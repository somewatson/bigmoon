import os
import logging
import sys
import argparse
import signal
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import requests
try:
    import psutil
except ImportError:
    psutil = None

from models import db, User, Favorite, DownloadTask
from downloader import start_download_async, start_compress_async, cancel_task, update_task_progress, shutdown_all_tasks, get_log_path



load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'big-moon-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:////app/data/users.db')
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

class PollingFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.last_logged = 0
        self.interval = 60

    def filter(self, record):
        # Werkzeug logs request paths in the message
        if 'GET /api/tasks' in record.getMessage():
            now = time.time()
            if now - self.last_logged < self.interval:
                return False
            self.last_logged = now
        return True

# Apply filter to werkzeug logger to silence frequent polling logs
logging.getLogger('werkzeug').addFilter(PollingFilter())

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def cleanup_temp_files():
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    try:
        files = os.listdir(downloads_dir)
        temp_files = [f for f in files if f.endswith('.temp.mp4') or f.endswith('.temp')]
        for f in temp_files:
            os.remove(os.path.join(downloads_dir, f))
        
        # Also clean up orphaned thumbnails
        thumb_dir = os.path.join(downloads_dir, '.thumbnails')
        if os.path.exists(thumb_dir):
            thumb_files = os.listdir(thumb_dir)
            actual_files = set(files)
            for tf in thumb_files:
                # If the thumbnail is for a file that no longer exists, delete it
                original_filename = tf.replace('.jpg', '')
                if original_filename not in actual_files:
                    os.remove(os.path.join(thumb_dir, tf))
                    
        if temp_files:
            logging.info(f"Cleaned up {len(temp_files)} temporary files from {downloads_dir}")
    except Exception as e:
        logging.error(f"Error cleaning up temp files: {e}")

def bootstrap_admin():
    with app.app_context():
        db.create_all()
        
        # Cleanup temporary files on startup
        cleanup_temp_files()
        
        # Migration: Add error_log column to DownloadTask if it doesn't exist
        try:
            db.session.execute(db.text("ALTER TABLE download_task ADD COLUMN error_log TEXT"))
            db.session.commit()
            app.logger.info("Migrated database: added error_log column to download_task")
        except Exception as e:
            # If column already exists, SQLite will throw an error; we can safely ignore it
            db.session.rollback()
            app.logger.debug(f"Database migration note: {e}")

        try:
            db.session.execute(db.text("ALTER TABLE download_task ADD COLUMN encoder_type TEXT"))
            db.session.commit()
            app.logger.info("Migrated database: added encoder_type column to download_task")
        except Exception as e:
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

        # Startup Cleanup: Mark all hanging tasks from previous session as error
        hanging_tasks = DownloadTask.query.filter(
            DownloadTask.status.in_(['pending', 'downloading', 'processing'])
        ).all()
        if hanging_tasks:
            app.logger.info(f"Cleaning up {len(hanging_tasks)} hanging tasks from previous session...")
            for task in hanging_tasks:
                task.status = 'error'
                task.error_log = 'Session restarted - task invalidated'
            db.session.commit()

def handle_shutdown(signum, frame):
    logging.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_all_tasks()
    sys.exit(0)

@app.before_request
def add_asset_version():
    # Add a global version to be used in templates for cache busting
    # In a real production app, this could be a git commit hash or a version number
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

@app.route('/api/admin/users', methods=['GET'])
@login_required
def admin_users_list():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    users = User.query.all()
    return jsonify({'users': [{'username': u.username, 'role': u.role} for u in users]})

@app.route('/admin/delete_user', methods=['POST'])
@login_required
def delete_user():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.json
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent deleting the last admin or yourself
    if user.role == 'admin' and User.query.filter_by(role='admin').count() <= 1:
        return jsonify({'error': 'Cannot delete the last administrator'}), 400
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
        
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {username} deleted successfully'})

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

@app.route('/api/thumbnails/<path:filename>')
@login_required
def get_thumbnail(filename):
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    thumb_dir = os.path.join(downloads_dir, '.thumbnails')
    
    # Ensure thumbnail directory exists
    if not os.path.exists(thumb_dir):
        try:
            os.makedirs(thumb_dir, exist_ok=True)
        except Exception as e:
            return jsonify({'error': f'Could not create thumbnail directory: {str(e)}'}), 500

    thumb_filename = f"{filename}.jpg"
    thumb_path = os.path.join(thumb_dir, thumb_filename)
    video_path = os.path.join(downloads_dir, filename)

    # Check if cached thumbnail exists
    if os.path.exists(thumb_path):
        return send_from_directory(thumb_dir, thumb_filename)

    # Verify video file exists
    if not os.path.exists(video_path):
        return jsonify({'error': 'Video file not found'}), 404

    # Generate thumbnail using FFmpeg
    # -ss 00:00:05: seek to 5 seconds
    # -i: input file
    # -vframes 1: extract one frame
    # -q:v 2: high quality
    # -vf scale=160:-1: scale to 160px width, keep aspect ratio
    try:
        import subprocess
        cmd = [
            'ffmpeg', '-y', 
            '-ss', '00:00:05', 
            '-i', video_path, 
            '-vframes', '1', 
            '-q:v', '2', 
            '-vf', 'scale=160:-1', 
            thumb_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return send_from_directory(thumb_dir, thumb_filename)
    except Exception as e:
        return jsonify({'error': f'Thumbnail generation failed: {str(e)}'}), 500

@app.route('/api/system/metrics')
@login_required
def system_metrics():
    if psutil is None:
        return jsonify({'error': 'psutil not installed'}), 500
    
    try:
        return jsonify({
            'cpu': psutil.cpu_percent(interval=None),
            'memory': psutil.virtual_memory().percent
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/cancel/<int:task_id>', methods=['POST'])
@login_required
def cancel_task_route(task_id):
    task = DownloadTask.query.get(task_id)
    if not task or task.user_id != current_user.id:
        return jsonify({'error': 'Task not found or unauthorized'}), 404
    
    if task.status in ['completed', 'error']:
        return jsonify({'error': 'Cannot cancel a finished task'}), 400
    
    if cancel_task(task_id):
        update_task_progress(task_id, 'error', error_log="Task cancelled by user")
        return jsonify({'message': 'Task cancelled successfully'})
    else:
        return jsonify({'error': 'Task could not be cancelled (possibly already finished)'}), 500

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
        
        return jsonify({'channel': user_data[0], 'videos': videos})
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

@app.route('/api/tasks/<int:task_id>/logs')
@login_required
def task_logs(task_id):
    task = DownloadTask.query.get(task_id)
    if not task or task.user_id != current_user.id:
        return jsonify({'error': 'Task not found or unauthorized'}), 404
    
    log_path = get_log_path(task_id)
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r') as f:
                logs = f.read()
            return jsonify({'logs': logs})
        except Exception as e:
            return jsonify({'error': f'Could not read log file: {str(e)}'}), 500
    
    return jsonify({'logs': task.error_log or 'No logs available yet.'})

@app.route('/api/tasks/clear_failed', methods=['POST'])
@login_required
def clear_failed_tasks():
    try:
        # Clear tasks that are in 'error' status OR are stuck in pending/downloading/processing
        count = DownloadTask.query.filter(
            DownloadTask.user_id == current_user.id,
            DownloadTask.status != 'completed'
        ).delete()
        db.session.commit()
        return jsonify({'message': f'Cleared {count} incomplete or failed tasks'})
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
            'error': t.error_log,
            'encoder_type': t.encoder_type
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
        # Filter out temp files and hidden files
        filtered_files = [f for f in files if not (f.endswith('.temp.mp4') or f.endswith('.temp') or f.startswith('.'))]
        
        # Filter for the user's files or allow all if admin
        user_files = [f for f in filtered_files if any(t.filename == f for t in DownloadTask.query.filter_by(user_id=current_user.id).all())]
        if current_user.role == 'admin':
            user_files = filtered_files
        return jsonify({'files': user_files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/library', methods=['GET'])
@login_required
def list_library():
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    try:
        all_files = os.listdir(downloads_dir)
    except Exception as e:
        return jsonify({'error': f'Could not access downloads directory: {str(e)}'}), 500
    
    # Filter out temp files and hidden files
    actual_files = [f for f in all_files if not (f.endswith('.temp.mp4') or f.endswith('.temp') or f.startswith('.'))]
    
    files_data = []
    for filename in actual_files:
        # Find the most recent task associated with this filename
        task = DownloadTask.query.filter_by(filename=filename).order_by(DownloadTask.created_at.desc()).first()
        
        # Access Control: If no task found, only admin can see/manage it
        if not task:
            if current_user.role != 'admin':
                continue
        elif task.user_id != current_user.id and current_user.role != 'admin':
            continue

        path = os.path.join(downloads_dir, filename)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue

        original_size = "Unknown"
        task_type = "unknown"
        encoder_type = None
        created_at = None

        if task:
            task_type = task.task_type
            encoder_type = task.encoder_type
            created_at = task.created_at
            
            if task.task_type == 'compress':
                parts = filename.split('_', 3)
                if len(parts) >= 4:
                    original_filename = parts[3]
                    orig_path = os.path.join(downloads_dir, original_filename)
                    if os.path.exists(orig_path):
                        try:
                            original_size = os.path.getsize(orig_path)
                        except OSError:
                            pass

        files_data.append({
            'filename': filename,
            'video_id': task.video_id if task else None,
            'type': task_type,
            'created_at': created_at,
            'size': format_size(size) if isinstance(size, (int, float)) else size,
            'original_size': format_size(original_size) if isinstance(original_size, (int, float)) else None,
            'savings': calculate_savings(original_size, size),
            'encoder_type': encoder_type
        })
    
    return jsonify({'files': files_data})

def calculate_savings(original, current):
    if not isinstance(original, (int, float)) or not isinstance(current, (int, float)):
        return None
    if original <= 0: return None
    saved = original - current
    percent = (saved / original) * 100
    return f"{format_size(saved)} ({round(percent, 1)}%)"

@app.route('/api/library/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_files():
    data = request.json
    filenames = data.get('filenames', [])
    if not filenames:
        return jsonify({'error': 'No files selected'}), 400
    
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    deleted_count = 0
    
    for filename in filenames:
        # Verify ownership
        task = DownloadTask.query.filter_by(filename=filename, user_id=current_user.id).first()
        if task or current_user.role == 'admin':
            path = os.path.join(downloads_dir, filename)
            try:
                if os.path.exists(path):
                    os.remove(path)
                    # Also remove task record to clean up library
                    if task:
                        db.session.delete(task)
                    
                    # Cleanup thumbnail if it exists
                    thumb_path = os.path.join(downloads_dir, '.thumbnails', f"{filename}.jpg")
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
                        
                    deleted_count += 1
            except Exception as e:
                app.logger.error(f"Error deleting {filename}: {e}")
    
    db.session.commit()
    return jsonify({'message': f'Successfully deleted {deleted_count} files'})

@app.route('/api/library/bulk-compress', methods=['POST'])
@login_required
def bulk_compress_files():
    data = request.json
    filenames = data.get('filenames', [])
    codec = data.get('codec', 'AV1')
    preset = data.get('preset', 'balanced')
    
    if not filenames:
        return jsonify({'error': 'No files selected'}), 400
    
    task_ids = []
    for filename in filenames:
        # Verify ownership
        task = DownloadTask.query.filter_by(filename=filename, user_id=current_user.id).first()
        if task or current_user.role == 'admin':
            # Create a new compression task
            new_task = DownloadTask(user_id=current_user.id, filename=filename, status='pending', task_type='compress')
            db.session.add(new_task)
            db.session.flush() # Get ID before commit
            
            start_compress_async(filename, preset, new_task.id, current_user.id, codec)
            task_ids.append(new_task.id)
    
    db.session.commit()
    return jsonify({'message': f'Started compression for {len(task_ids)} files', 'taskIds': task_ids})

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
    # Register signal handlers for SIGTERM (Docker stop) and SIGINT (Ctrl+C)
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    app.run(host='0.0.0.0', port=5000)
