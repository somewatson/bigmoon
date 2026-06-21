import os
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
    return render_template('admin.html')

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

@app.route('/api/tasks', methods=['GET'])
@login_required
def list_tasks():
    tasks = DownloadTask.query.filter_by(user_id=current_user.id).order_by(DownloadTask.created_at.desc()).all()
    return jsonify({
        'tasks': [{
            'id': t.id,
            'filename': t.filename,
            'status': t.status,
            'progress': t.progress,
            'type': t.task_type,
            'video_id': t.video_id
        } for t in tasks]
    })


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
    
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400
    
    # Create task record
    task = DownloadTask(user_id=current_user.id, filename=filename, status='pending', task_type='compress')
    db.session.add(task)
    db.session.commit()
    
    start_compress_async(filename, preset, task.id, current_user.id)
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
    return jsonify({
        'files': [{
            'filename': t.filename,
            'video_id': t.video_id,
            'type': t.task_type,
            'created_at': t.created_at
        } for t in tasks]
    })

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
