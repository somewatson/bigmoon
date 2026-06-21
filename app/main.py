import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import requests

from models import db, User
from downloader import start_download_async



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

@app.route('/api/download', methods=['POST'])
@login_required
def download_video():
    data = request.json
    url = data.get('url')
    video_id = data.get('id')
    
    if not url or not video_id:
        return jsonify({'error': 'URL and ID are required'}), 400
    
    start_download_async(url, video_id)
    return jsonify({'message': 'Download started in background'})


if __name__ == '__main__':
    bootstrap_admin()
    app.run(host='0.0.0.0', port=5000)
