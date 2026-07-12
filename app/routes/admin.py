import os
import subprocess
import shutil
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, User, DownloadTask
from utils.system import format_size

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Access denied", 403
    
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    disk_info = "Unknown"
    try:
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

@admin_bp.route('/admin/activity')
@login_required
def admin_activity():
    if current_user.role != 'admin':
        return "Access denied", 403
    return render_template('admin_activity.html')

@admin_bp.route('/api/admin/activity')
@login_required
def admin_activity_api():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        total_users = User.query.count()
        total_active = DownloadTask.query.filter(DownloadTask.status.in_(['pending', 'downloading', 'processing'])).count()
        total_pending = DownloadTask.query.filter_by(status='pending').count()
        total_failed = DownloadTask.query.filter_by(status='error').count()
        
        tasks_query = db.session.query(DownloadTask, User.username).join(User, DownloadTask.user_id == User.id).order_by(DownloadTask.created_at.desc()).all()
        
        tasks_list = []
        user_stats_map = {}

        for task, username in tasks_query:
            tasks_list.append({
                'id': task.id,
                'username': username,
                'video_id': task.video_id,
                'filename': task.filename,
                'status': task.status,
                'progress': task.progress,
                'created_at': task.created_at.isoformat() if task.created_at else None
            })
            
            if username not in user_stats_map:
                user_stats_map[username] = {'total': 0, 'completed': 0, 'failed': 0, 'last_active': task.created_at}
            
            user_stats_map[username]['total'] += 1
            if task.status == 'completed':
                user_stats_map[username]['completed'] += 1
            elif task.status == 'error':
                user_stats_map[username]['failed'] += 1
            
            if task.created_at and (not user_stats_map[username]['last_active'] or task.created_at > user_stats_map[username]['last_active']):
                user_stats_map[username]['last_active'] = task.created_at

        user_summaries = [
            {
                'username': name,
                'total_tasks': stats['total'],
                'completed_tasks': stats['completed'],
                'failed_tasks': stats['failed'],
                'last_active': stats['last_active'].isoformat() if stats['last_active'] else 'Never'
            }
            for name, stats in user_stats_map.items()
        ]
            
        return jsonify({
            'stats': {
                'total_users': total_users,
                'active_tasks': total_active,
                'pending_tasks': total_pending,
                'failed_tasks': total_failed
            },
            'tasks': tasks_list,
            'user_summaries': user_summaries
        })
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error fetching admin activity stats: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        return "Access denied", 403
    return render_template('admin_users.html')

@admin_bp.route('/api/admin/users', methods=['GET'])
@login_required
def admin_users_list():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    users = User.query.all()
    return jsonify({'users': [{'username': u.username, 'role': u.role} for u in users]})

@admin_bp.route('/admin/delete_user', methods=['POST'])
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
    
    if user.role == 'admin' and User.query.filter_by(role='admin').count() <= 1:
        return jsonify({'error': 'Cannot delete the last administrator'}), 400
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
        
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {username} deleted successfully'})

@admin_bp.route('/system/status')
@login_required
def system_status():
    if current_user.role != 'admin':
        return "Access denied", 403
    return render_template('system_status.html')

@admin_bp.route('/admin/create_user', methods=['POST'])
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

@admin_bp.route('/api/system/ffmpeg')
@login_required
def ffmpeg_status():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, check=True)
        encoders = result.stdout
        
        status = {
            'qsv': ('h264_qsv' in encoders or 'hevc_qsv' in encoders) and os.path.exists('/dev/dri/renderD128'),
            'nvenc': ('h264_nvenc' in encoders or 'hevc_nvenc' in encoders) and os.path.exists('/dev/nvidia0'),
            'vaapi': ('h264_vaapi' in encoders or 'hevc_vaapi' in encoders) and os.path.exists('/dev/dri/renderD128'),
            'amf': 'h264_amf' in encoders or 'hevc_amf' in encoders,
            'libx264': 'libx264' in encoders
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/system/metrics')
@login_required
def system_metrics():
    try:
        import psutil
    except ImportError:
        return jsonify({'error': 'psutil not installed'}), 500
    
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        
        if cpu == 0.0 and mem == 0.0:
            try:
                with open('/proc/meminfo', 'r') as f:
                    lines = f.readlines()
                    mem_total = 0
                    mem_available = 0
                    for line in lines:
                        if 'MemTotal:' in line:
                            mem_total = int(line.split()[1])
                        elif 'MemAvailable:' in line:
                            mem_available = int(line.split()[1])
                        if mem_total > 0:
                            mem = round(((mem_total - mem_available) / mem_total) * 100, 1)
            except:
                pass
        
        if cpu == 0.0 and mem == 0.0:
            return jsonify({'error': 'Metrics unavailable in this environment'}), 200
            
        return jsonify({
            'cpu': cpu,
            'memory': mem
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
