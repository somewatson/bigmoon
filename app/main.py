import os
import logging
import sys
import argparse
import signal
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import requests
from apscheduler.schedulers.background import BackgroundScheduler
try:
    import psutil
except ImportError:
    psutil = None

from models import db, User, Favorite, DownloadTask, MonitoredChannel, ChatMessage
from downloader import start_download_async, start_compress_async, cancel_task, update_task_progress, shutdown_all_tasks, get_log_path
from chat_manager import start_chat_download_async, download_chat_sync
from utils.system import cleanup_temp_files

# Import blueprints
from routes.admin import admin_bp
from routes.tasks import tasks_bp
from routes.library import library_bp
from routes.social import social_bp

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'big-moon-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:////app/data/users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true', help='Enable debug logging')
args, unknown = parser.parse_known_args()

log_level = logging.DEBUG if args.debug else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
app.logger.setLevel(log_level)

class PollingFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.last_logged = 0
        self.interval = 60

    def filter(self, record):
        if 'GET /api/tasks' in record.getMessage():
            now = time.time()
            if now - self.last_logged < self.interval:
                return False
            self.last_logged = now
        return True

logging.getLogger('werkzeug').addFilter(PollingFilter())

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register Blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(library_bp)
app.register_blueprint(social_bp)

def bootstrap_admin():
    with app.app_context():
        db.create_all()
        cleanup_temp_files()
        
        migrations = [
            "ALTER TABLE download_task ADD COLUMN error_log TEXT",
            "ALTER TABLE download_task ADD COLUMN chat_json_path TEXT",
            "ALTER TABLE download_task ADD COLUMN encoder_type TEXT",
            "ALTER TABLE download_task ADD COLUMN chat_status TEXT",
            "ALTER TABLE download_task ADD COLUMN last_byte_offset INTEGER",
            "ALTER TABLE download_task ADD COLUMN url TEXT"
        ]
        for sql in migrations:
            try:
                db.session.execute(db.text(sql))
                db.session.commit()
            except Exception:
                db.session.rollback()

        try:
            db.session.execute(db.text("CREATE TABLE IF NOT EXISTS monitored_channel (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, channel_name TEXT NOT NULL, twitch_user_id TEXT, enabled BOOLEAN DEFAULT 1, auto_compress BOOLEAN DEFAULT 0, compression_presets TEXT DEFAULT '', target_codec TEXT DEFAULT 'AV1', delete_original BOOLEAN DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES user(id))"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Failed to create monitored_channel table: {e}")

        recover_interrupted_tasks()

def recover_interrupted_tasks():
    app.logger.info("Starting Recovery Manager: checking for interrupted tasks...")
    interrupted_tasks = DownloadTask.query.filter(
        DownloadTask.status.in_(['paused', 'downloading', 'processing'])
    ).all()
    
    if not interrupted_tasks:
        app.logger.info("No interrupted tasks found for recovery.")
        return
    
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    recovered_count = 0
    
    for task in interrupted_tasks:
        try:
            resumable = False
            if task.task_type == 'download':
                if task.filename and os.path.exists(os.path.join(downloads_dir, task.filename)):
                    resumable = True
                elif task.video_id:
                    temp_files = [f for f in os.listdir(downloads_dir) if task.video_id in f and f.endswith(('.part', '.ytdl'))]
                    if temp_files:
                        resumable = True
            elif task.task_type == 'compress':
                if task.filename and os.path.exists(os.path.join(downloads_dir, task.filename)):
                    resumable = True
            
            if resumable:
                task.status = 'pending'
                db.session.commit()
                if task.task_type == 'download':
                    if task.url:
                        # Truly resume the download
                        from app.downloader import start_download_async
                        start_download_async(task.url, task.video_id, task.id)
                        recovered_count += 1
                    else:
                        task.status = 'error'
                        task.error_log = "Recovery failed: original URL not found in database."
                elif task.task_type == 'compress':
                    start_compress_async(task.filename, 'balanced', task.id, task.user_id, 'H.264')
                    recovered_count += 1
                db.session.commit()
            else:
                task.status = 'error'
                task.error_log = "Recovery failed: no partial file found on disk."
                db.session.commit()
        except Exception as e:
            app.logger.error(f"Error recovering task {task.id}: {e}")
            db.session.rollback()
    
    app.logger.info(f"Recovery sequence completed. {recovered_count} tasks resumed.")

def handle_shutdown(signum, frame):
    logging.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_all_tasks()
    sys.exit(0)

@app.before_request
def add_asset_version():
    from flask import g
    g.asset_version = int(time.time())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    tab = request.args.get('tab', 'search')
    return render_template('index.html', current_tab=tab)

def get_twitch_token_internal():
    from utils.system import get_twitch_token
    return get_twitch_token()

def check_for_new_vods():
    with app.app_context():
        logging.info("Checking for new VODs across monitored channels...")
        try:
            monitored_channels = MonitoredChannel.query.filter_by(enabled=True).all()
            if not monitored_channels:
                return

            token = get_twitch_token_internal()
            headers = {
                'Client-ID': os.getenv('TWITCH_CLIENT_ID'),
                'Authorization': f'Bearer {token}'
            }

            for channel in monitored_channels:
                user_id = channel.twitch_user_id
                if not user_id:
                    user_res = requests.get(f'https://api.twitch.tv/helix/users?login={channel.channel_name}', headers=headers)
                    user_res.raise_for_status()
                    user_data = user_res.json().get('data')
                    if not user_data: continue
                    user_id = user_data[0]['id']
                    channel.twitch_user_id = user_id
                    db.session.commit()

                vod_res = requests.get(f'https://api.twitch.tv/helix/videos?user_id={user_id}', headers=headers)
                vod_res.raise_for_status()
                videos = vod_res.json().get('data', [])

                now = datetime.utcnow()
                twenty_four_hours_ago = now - timedelta(hours=24)
                for video in videos:
                    video_id = video['id']
                    created_at = datetime.strptime(video['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if not (created_at >= twenty_four_hours_ago or created_at >= channel.created_at):
                        continue
                    if DownloadTask.query.filter_by(video_id=video_id).first():
                        continue
                    
                    task = DownloadTask(user_id=channel.user_id, video_id=video_id, status='pending', task_type='download')
                    db.session.add(task)
                    db.session.commit()
                    start_download_async(video['url'], video_id, task.id)
                    start_chat_download_async(video_id, task.id)
        except Exception as e:
            logging.error(f"Error in background monitoring worker: {e}")

def setup_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_for_new_vods, trigger='interval', minutes=30)
    scheduler.start()
    return scheduler

if __name__ == '__main__':
    bootstrap_admin()
    scheduler = setup_scheduler()
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    app.run(host='0.0.0.0', port=5000)
