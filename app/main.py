import os
import logging
import sys
import argparse
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import requests

from models import db, User, Favorite, DownloadTask
from downloader import start_download_async, start_compress_async



load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'big-moon-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///data/users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Handle command line arguments for logging
parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true', help='Enable debug logging')
args, unknown = parser.parse_known_args()

log_level = logging.DEBUG if args.debug else logging.INFO

logging.basicConfig(
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
app.logger.setLevel(log_level)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def bootstrap_admin():
    with app.app_context():
        db.create_all()
        
        # Migration: Add error_log column to DownloadTask if it doesn't exist
        try:
            db.session.execute(db.text("ALTER TABLE download_task ADD COLUMN error_log TEXT"))
            db.session.commit()
            app.logger.info("Migrated database: added error_log column to download_task")
        except Exception as e:
            # If column already exists, SQLite will throw an error; we can safely ignore it
            db.session.rollback()
            app.logger.debug(f"Database migration note: {e}")

        if not User.query.filter_by(role='admin').first():
            admin_user = User(
                username=os.getenv('ADMIN_USERNAME', 'admin'),
                role='admin'
            )
            admin_user.set_password(os.getenv('ADMIN_PASSWORD', 'admin_password'))
            db.session.add(admin_user)
            db.session.commit()

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

@app.route('/api/system/ffmpeg')
@login_required
def ffmpeg_status():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, check=True)
        encoders = result.stdout
        
        # Check for common HW accelerators
        status = {
            'qsv': 'h264_qsv' in encoders or 'hevc_qsv' in encoders,
            'nvenc': 'h264_nvenc' in encoders or 'hevc_nvenc' in encoders,
            'vaapi': 'h264_vaapi' in encoders or 'hevc_vaapi' in encoders,
            'amf': 'h264_amf' in encoders or 'hevc_amf' in encoders,
            'libx264': 'libx264' in encoders
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Access denied", 403
    
    # Basic system stats
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    disk_info = "Unknown"
    try:
        import shutil
        total, used, free = shutil.disk_usage(downloads_dir)
        disk_info = f"{format_size(used)} used / {format_size(total)} total"
    except Exception:
        pass

    user_count = User.query.count()
    task_count = DownloadTask.query.count()
    
    return render_template('admin_dashboard.html', 
                           disk_info=disk_info, 
                           user_count=user_count, 
                           task_count=task_count)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        return "Access denied", 403
    return render_template('admin_users.html')

@app.route('/system/status')
@login_required
def system_status():
    if current_user.role != 'admin':
        return "Access denied", 403
    return render_template('system_status.html')

@app.route('/admin/create_user', methods=['POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'user')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'User already exists'}), 400

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': f'User {username} created successfully'})

def get_twitch_token():
    client_id = os.getenv('TWITCH_CLIENT_ID')
    client_secret = os.getenv('TWITCH_CLIENT_SECRET')
    url = f'https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials'
    response = requests.post(url)
    response.raise_for_status()
    return response.json()['access_token']

@app.route('/api/videos', methods=['POST'])
@login_required
def list_videos():
    channel_name = request.json.get('channel')
    if not channel_name:
        return jsonify({'error': 'Channel name is required'}), 400
    
    try:
        token = get_twitch_token()
        headers = {
            'Client-ID': os.getenv('TWITCH_CLIENT_ID'),
            'Authorization': f'Bearer {token}'
        }
        
        # 1. Get User ID
        user_res = requests.get(f'https://api.twitch.tv/helix/users?login={channel_name}', headers=headers)
        user_res.raise_for_status()
        user_data = user_res.json().get('data')
        if not user_data:
            return jsonify({'error': 'Channel not found'}), 404
        
        user_id = user_data[0]['id']
        
        # 2. Get VODs
        vod_res = requests.get(f'https://api.twitch.tv/helix/videos?user_id={user_id}', headers=headers)
        vod_res.raise_for_status()
        videos = vod_res.json().get('data', [])
        
        return jsonify({'videos': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorites', methods=['GET', 'POST'])
@login_required
def manage_favorites():
    if request.method == 'POST':
        data = request.json
        channel = data.get('channel')
        if not channel:
            return jsonify({'error': 'Channel name required'}), 400
        
        # Toggle favorite
        fav = Favorite.query.filter_by(user_id=current_user.id, channel_name=channel).first()
        if fav:
            db.session.delete(fav)
            db.session.commit()
            return jsonify({'status': 'removed'})
        else:
            new_fav = Favorite(user_id=current_user.id, channel_name=channel)
            db.session.add(new_fav)
            db.session.commit()
            return jsonify({'status': 'added'})
            
    # GET all favorites
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    return jsonify({'favorites': [f.channel_name for f in favs]})

def format_size(size_bytes):
    if size_bytes == 0: return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

@app.route('/api/tasks/clear_failed', methods=['POST'])
@login_required
def clear_failed_tasks():
    try:
        count = DownloadTask.query.filter_by(user_id=current_user.id, status='error').delete()
        db.session.commit()
        return jsonify({'message': f'Cleared {count} failed tasks'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks', methods=['GET'])
@login_required
def list_tasks():
    tasks = DownloadTask.query.filter_by(user_id=current_user.id).order_by(DownloadTask.created_at.desc()).all()
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    
    task_list = []
    for t in tasks:
        size = "Calculating..."
        if t.filename:
            path = os.path.join(downloads_dir, t.filename)
            if os.path.exists(path):
                size = format_size(os.path.getsize(path))
        
        task_list.append({
            'id': t.id,
            'filename': t.filename,
            'status': t.status,
            'progress': t.progress,
            'type': t.task_type,
            'video_id': t.video_id,
            'size': size,
            'error': t.error_log
        })
    return jsonify({'tasks': task_list})


@app.route('/api/download', methods=['POST'])
@login_required
def download_video():
    data = request.json
    url = data.get('url')
    video_id = data.get('id')
    
    if not url or not video_id:
        return jsonify({'error': 'URL and ID are required'}), 400
    
    # Create task record
    task = DownloadTask(user_id=current_user.id, video_id=video_id, status='pending', task_type='download')
    db.session.add(task)
    db.session.commit()
    
    start_download_async(url, video_id, task.id)
    return jsonify({'message': 'Download started in background', 'taskId': task.id})

@app.route('/api/compress', methods=['POST'])
@login_required
def compress_video():
    data = request.json
    filename = data.get('filename')
    preset = data.get('preset', 'balanced')
    codec = data.get('codec', 'H.264')
    
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400
    
    # Create task record
    task = DownloadTask(user_id=current_user.id, filename=filename, status='pending', task_type='compress')
    db.session.add(task)
    db.session.commit()
    
    start_compress_async(filename, preset, task.id, current_user.id, codec)
    return jsonify({'message': 'Compression started in background', 'taskId': task.id})

@app.route('/api/files', methods=['GET'])
@login_required
def list_files():
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    try:
        files = os.listdir(downloads_dir)
        # Filter for the user's files or allow all if admin
        user_files = [f for f in files if any(t.filename == f for t in DownloadTask.query.filter_by(user_id=current_user.id).all())]
        if current_user.role == 'admin':
            user_files = files
        return jsonify({'files': user_files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/library', methods=['GET'])
@login_required
def list_library():
    tasks = DownloadTask.query.filter_by(user_id=current_user.id, status='completed').all()
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    
    files = []
    for t in tasks:
        size = "Unknown"
        if t.filename:
            path = os.path.join(downloads_dir, t.filename)
            if os.path.exists(path):
                size = format_size(os.path.getsize(path))
                
        files.append({
            'filename': t.filename,
            'video_id': t.video_id,
            'type': t.task_type,
            'created_at': t.created_at,
            'size': size
        })
    return jsonify({'files': files})

@app.route('/downloads/<path:filename>')
@login_required
def download_file(filename):
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    # Verify user owns this file
    task = DownloadTask.query.filter_by(filename=filename, user_id=current_user.id).first()
    if not task and current_user.role != 'admin':
        return "Unauthorized", 403
    
    return send_from_directory(downloads_dir, filename, as_attachment=True)

if __name__ == '__main__':
    bootstrap_admin()
    app.run(host='0.0.0.0', port=5000)
