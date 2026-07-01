import os
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, DownloadTask
from downloader import start_download_async, start_compress_async, cancel_task, update_task_progress, get_log_path
from utils.system import format_size

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/api/tasks/retry/<int:task_id>', methods=['POST'])
@login_required
def retry_task(task_id):
    task = DownloadTask.query.get(task_id)
    if not task or task.user_id != current_user.id:
        return jsonify({'error': 'Task not found or unauthorized'}), 404
    
    if task.status not in ['error', 'cancelled']:
        return jsonify({'error': 'Only failed or cancelled tasks can be retried'}), 400

    if task.task_type == 'download':
        if not task.url:
            error_msg = 'This is a legacy task and its original URL was not stored. Please re-add the VOD to the queue.'
            update_task_progress(task.id, error_log=error_msg)
            return jsonify({'error': error_msg}), 400
        
        from app.downloader import start_download_async
        start_download_async(task.url, task.video_id, task.id)
        update_task_progress(task.id, 'pending', progress=0.0)
        return jsonify({'message': 'Download retry started'})
    
    elif task.task_type == 'compress':

        if not task.filename:
            return jsonify({'error': 'Input file missing, cannot retry compression'}), 400
        
        start_compress_async(task.filename, 'balanced', task.id, current_user.id, 'H.264')
        update_task_progress(task.id, 'pending', progress=0.0)
        return jsonify({'message': 'Compression retry started'})
    
    return jsonify({'error': 'Unknown task type'}), 400

@tasks_bp.route('/api/tasks/cancel/<int:task_id>', methods=['POST'])
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

@tasks_bp.route('/api/tasks/<int:task_id>/logs')
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

@tasks_bp.route('/api/tasks/clear_failed', methods=['POST'])
@login_required
def clear_failed_tasks():
    try:
        count = DownloadTask.query.filter(
            DownloadTask.user_id == current_user.id,
            DownloadTask.status == 'error'
        ).delete()
        db.session.commit()
        return jsonify({'message': f'Cleared {count} incomplete or failed tasks'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks', methods=['GET'])
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

@tasks_bp.route('/api/download', methods=['POST'])
@login_required
def download_video():
    data = request.json
    url = data.get('url')
    video_id = data.get('id')
    
    if not url or not video_id:
        return jsonify({'error': 'URL and ID are required'}), 400
    
    task = DownloadTask(user_id=current_user.id, url=url, video_id=video_id, status='pending', task_type='download')
    db.session.add(task)
    db.session.commit()
    
    start_download_async(url, video_id, task.id)
    from chat_manager import start_chat_download_async
    start_chat_download_async(video_id, task.id)
    return jsonify({'message': 'Download started in background', 'taskId': task.id})

@tasks_bp.route('/api/compress', methods=['POST'])
@login_required
def compress_video():
    data = request.json
    filename = data.get('filename')
    preset = data.get('preset', 'balanced')
    codec = data.get('codec', 'H.264')
    
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400

    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    output_filename = f"compressed_{codec}_{preset}_{filename}"
    if os.path.exists(os.path.join(downloads_dir, output_filename)):
        return jsonify({'error': 'A compressed version with these settings already exists', 'exists': True}), 409
    
    task = DownloadTask(user_id=current_user.id, filename=filename, status='pending', task_type='compress')
    db.session.add(task)
    db.session.commit()
    
    start_compress_async(filename, preset, task.id, current_user.id, codec)
    return jsonify({'message': 'Compression started in background', 'taskId': task.id})
