import os
import subprocess
import threading
import re
from dotenv import load_dotenv
from models import db, DownloadTask

load_dotenv()

DOWNLOADS_DIR = os.getenv('DOWNLOADS_DIR', '/app/downloads')
USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'

def update_task_progress(task_id, status=None, progress=None, filename=None):
    from main import app
    with app.app_context():
        try:
            task = DownloadTask.query.get(task_id)
            if task:
                if status is not None: task.status = status
                if progress is not None: task.progress = progress
                if filename is not None: task.filename = filename
                db.session.commit()
        except Exception as e:
            print(f"Database error updating task {task_id}: {e}")

def cleanup_temp_files():
    """Removes yt-dlp temporary files from the downloads directory."""
    try:
        for file in os.listdir(DOWNLOADS_DIR):
            if file.endswith(('.part', '.temp', '.ytdl')):
                os.remove(os.path.join(DOWNLOADS_DIR, file))
    except Exception as e:
        print(f"Error during cleanup: {e}")

def download_vod(url, video_id, task_id):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    
    cmd = [
        'yt-dlp',
        '--newline',
        '-o', f'{DOWNLOADS_DIR}/%(title)s [%(id)s].%(ext)s',
        url
    ]
    
    if USE_GPU:
        cmd.extend(['--postprocessor-args', 'ffmpeg:-c:v h264_qsv'])
    
    update_task_progress(task_id, 'downloading')
    
    try:
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1,
            universal_newlines=True
        )
        
        progress_re = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
        filename = None

        # Read output line by line
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            
            # Debug print to see what yt-dlp is actually saying
            print(f"yt-dlp output: {line.strip()}")
            
            match = progress_re.search(line)
            if match:
                progress = float(match.group(1))
                update_task_progress(task_id, progress=progress)
            
            if '[download] Destination:' in line:
                filename = line.split('Destination: ')[-1].strip()
                update_task_progress(task_id, filename=filename)

        process.wait()
        if process.returncode == 0:
            update_task_progress(task_id, 'completed', progress=100.0)
            cleanup_temp_files()
        else:
            update_task_progress(task_id, 'error')
            cleanup_temp_files()
            
    except Exception as e:
        print(f"Error downloading {video_id}: {e}")
        update_task_progress(task_id, 'error')
        cleanup_temp_files()

def compress_video(input_filename, preset, task_id, user_id):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    input_path = os.path.join(DOWNLOADS_DIR, input_filename)
    output_filename = f"compressed_{preset}_{input_filename}"
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    
    presets = {
        'fast': {'bitrate': '2M', 'preset': 'veryfast'},
        'balanced': {'bitrate': '5M', 'preset': 'medium'},
        'high': {'bitrate': '10M', 'preset': 'slow'}
    }
    
    p = presets.get(preset, presets['balanced'])
    
    cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-c:v', 'h264_qsv',
        '-b:v', p['bitrate'],
        '-preset', p['preset'],
        '-c:a', 'copy',
        output_path
    ]
    
    update_task_progress(task_id, 'processing')
    
    try:
        # Use capture_output to get stdout and stderr for logging
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        update_task_progress(task_id, 'completed', progress=100.0, filename=output_filename)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error for {input_filename}:")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        update_task_progress(task_id, 'error')
    except Exception as e:
        print(f"Unexpected Error compressing {input_filename}: {e}")
        update_task_progress(task_id, 'error')

def start_download_async(url, video_id, task_id):
    thread = threading.Thread(target=download_vod, args=(url, video_id, task_id))
    thread.start()
    return thread

def start_compress_async(input_filename, preset, task_id, user_id):
    thread = threading.Thread(target=compress_video, args=(input_filename, preset, task_id, user_id))
    thread.start()
    return thread
