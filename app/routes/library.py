import os
import subprocess
from flask import Blueprint, render_template, request, jsonify, send_from_directory
from flask_login import login_required, current_user
from models import db, DownloadTask
from utils.system import format_size
from urllib.parse import unquote

library_bp = Blueprint('library', __name__)

@library_bp.route('/api/thumbnails/<path:filename>')
@login_required
def get_thumbnail(filename):
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    thumb_dir = os.path.join(downloads_dir, '.thumbnails')
    
    if not os.path.exists(thumb_dir):
        try:
            os.makedirs(thumb_dir, exist_ok=True)
        except Exception as e:
            return jsonify({'error': f'Could not create thumbnail directory: {str(e)}'}), 500

    decoded_filename = unquote(filename)
    thumb_filename = f"{decoded_filename}.jpg"
    thumb_path = os.path.join(thumb_dir, thumb_filename)
    video_path = os.path.join(downloads_dir, decoded_filename)

    if os.path.exists(thumb_path):
        return send_from_directory(thumb_dir, thumb_filename)

    if not os.path.exists(video_path):
        return jsonify({'error': 'Video file not found'}), 404

    try:
        cmd = [
            'ffmpeg', '-y', 
            '-ss', '00:00:05', 
            '-i', video_path, 
            '-vframes', '1', 
            '-q:v', '2', 
            '-vf', 'scale=160:-1', 
            thumb_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return send_from_directory(thumb_dir, thumb_filename)
    except Exception as e:
        return jsonify({'error': f'Thumbnail generation failed: {str(e)}'}), 500

@library_bp.route('/api/files', methods=['GET'])
@login_required
def list_files():
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    try:
        files = os.listdir(downloads_dir)
        filtered_files = [f for f in files if not (f.endswith('.temp.mp4') or f.endswith('.temp') or f.startswith('.'))]
        
        user_files = [f for f in filtered_files if any(t.filename == f for t in DownloadTask.query.filter_by(user_id=current_user.id).all())]
        if current_user.role == 'admin':
            user_files = filtered_files
            
        files_data = []
        for filename in user_files:
            task = DownloadTask.query.filter_by(filename=filename).first()
            
            path = os.path.join(downloads_dir, filename)
            try:
                size_bytes = os.path.getsize(path)
                size = format_size(size_bytes)
            except OSError:
                size = 'Unknown'
            
            if task:
                created_at = task.created_at
                video_id = task.video_id
            else:
                try:
                    created_at = __import__('datetime').datetime.fromtimestamp(os.path.getmtime(path))
                except OSError:
                    created_at = None
                video_id = None
                
            files_data.append({
                'filename': filename,
                'size': size,
                'size_bytes': size_bytes if 'size_bytes' in locals() else 0,
                'created_at': created_at,
                'video_id': video_id
            })
            
        return jsonify({'files': files_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@library_bp.route('/api/library', methods=['GET'])
@login_required
def list_library():
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    try:
        all_files = os.listdir(downloads_dir)
    except Exception as e:
        return jsonify({'error': f'Could not access downloads directory: {str(e)}'}), 500
    
    actual_files = [f for f in all_files if not (f.endswith(('.temp.mp4', '.temp', '.part', '.ytdl')) or f.startswith('.'))]
    
    files_data = []
    for filename in actual_files:
        task = DownloadTask.query.filter_by(filename=filename).order_by(DownloadTask.created_at.desc()).first()
        
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
        
        if filename.startswith('compressed_'):
            task_type = 'compress'
            parts = filename.split('_', 3)
            if len(parts) >= 4:
                original_filename = parts[3]
                orig_path = os.path.join(downloads_dir, original_filename)
                if os.path.exists(orig_path):
                    try:
                        original_size = os.path.getsize(orig_path)
                    except OSError:
                        pass
        else:
            task_type = 'download'

        if task:
            encoder_type = task.encoder_type
            created_at = task.created_at
        else:
            try:
                created_at = __import__('datetime').datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                created_at = None
        
        files_data.append({
            'filename': filename,
            'video_id': task.video_id if task else None,
            'type': task_type,
            'created_at': created_at,
            'size': format_size(size) if isinstance(size, (int, float)) else size,
            'size_bytes': size if isinstance(size, (int, float)) else 0,
            'original_size': format_size(original_size) if isinstance(original_size, (int, float)) else None,
            'original_size_bytes': original_size if isinstance(original_size, (int, float)) else 0,
            'savings': calculate_savings_internal(original_size, size),
            'encoder_type': encoder_type
        })
    
    return jsonify({'files': files_data})

def calculate_savings_internal(original, current):
    from utils.system import calculate_savings
    return calculate_savings(original, current)

@library_bp.route('/api/library/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_files():
    data = request.json
    filenames = data.get('filenames', [])
    if not filenames:
        return jsonify({'error': 'No files selected'}), 400
    
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    deleted_count = 0
    
    for filename in filenames:
        task = DownloadTask.query.filter_by(filename=filename, user_id=current_user.id).first()
        if task or current_user.role == 'admin':
            path = os.path.join(downloads_dir, filename)
            try:
                if os.path.exists(path):
                    os.remove(path)
                    if task:
                        db.session.delete(task)
                    
                    thumb_path = os.path.join(downloads_dir, '.thumbnails', f"{filename}.jpg")
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
                        
                    deleted_count += 1
            except Exception as e:
                from flask import current_app
                current_app.logger.error(f"Error deleting {filename}: {e}")
    
    db.session.commit()
    return jsonify({'message': f'Successfully deleted {deleted_count} files'})

@library_bp.route('/api/library/bulk-compress', methods=['POST'])
@login_required
def bulk_compress_files():
    data = request.json
    filenames = data.get('filenames', [])
    codec = data.get('codec', 'AV1')
    preset = data.get('preset', 'balanced')
    
    if not filenames:
        return jsonify({'error': 'No files selected'}), 400

    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    task_ids = []
    skipped_files = []
    
    for filename in filenames:
        task = DownloadTask.query.filter_by(filename=filename, user_id=current_user.id).first()
        if task or current_user.role == 'admin':
            output_filename = f"compressed_{codec}_{preset}_{filename}"
            if os.path.exists(os.path.join(downloads_dir, output_filename)):
                skipped_files.append(filename)
                continue

            new_task = DownloadTask(user_id=current_user.id, filename=filename, status='pending', task_type='compress')
            db.session.add(new_task)
            db.session.flush()
            
            from downloader import start_compress_async
            start_compress_async(filename, preset, new_task.id, current_user.id, codec)
            task_ids.append(new_task.id)
    
    db.session.commit()
    
    message = f'Started compression for {len(task_ids)} files'
    if skipped_files:
        message += f'. Skipped {len(skipped_files)} files that already had compressed copies.'
        
    return jsonify({'message': message, 'taskIds': task_ids, 'skipped': skipped_files})

@library_bp.route('/api/preview/<path:filename>')
@login_required
def preview_video(filename):
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    decoded_filename = unquote(filename)
    safe_filename = os.path.basename(decoded_filename)
    
    # Check if this is a numeric video_id instead of a filename
    is_video_id = safe_filename.isdigit()
    
    # If it's a video_id or the file doesn't exist on disk, we can't serve local preview
    video_path = os.path.join(downloads_dir, safe_filename)
    if is_video_id or not os.path.exists(video_path):
        # Instead of 404, return a hint that this should be viewed via Twitch player
        return jsonify({'error': 'Local file not available', 'use_twitch_player': True}), 404

    return send_from_directory(downloads_dir, safe_filename)

@library_bp.route('/downloads/<path:filename>')
@login_required
def download_file(filename):
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    decoded_filename = unquote(filename)
    task = DownloadTask.query.filter_by(filename=decoded_filename, user_id=current_user.id).first()
    if not task and current_user.role != 'admin':
        return "Unauthorized", 403
    
    return send_from_directory(downloads_dir, decoded_filename, as_attachment=True)
