from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_name = db.Column(db.String(100), nullable=False)

class DownloadTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    url = db.Column(db.Text)
    video_id = db.Column(db.String(100), index=True)
    filename = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')
    progress = db.Column(db.Float, default=0.0)
    task_type = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    error_log = db.Column(db.Text)
    encoder_type = db.Column(db.String(10))
    last_byte_offset = db.Column(db.BigInteger, default=0)
    chat_json_path = db.Column(db.String(255))
    chat_status = db.Column(db.String(20), default='pending')

class MonitoredChannel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_name = db.Column(db.String(100), nullable=False)
    twitch_user_id = db.Column(db.String(100))
    enabled = db.Column(db.Boolean, default=True)
    auto_compress = db.Column(db.Boolean, default=False)
    compression_presets = db.Column(db.String(255), default='')  # Comma-separated presets
    target_codec = db.Column(db.String(20), default='AV1')
    delete_original = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('download_task.id'), nullable=False)
    username = db.Column(db.String(100))
    message = db.Column(db.Text)
    time_in_seconds = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)

