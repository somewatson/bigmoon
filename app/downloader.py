import os
import subprocess
import threading
import re
from dotenv import load_dotenv
from models import db, DownloadTask

load_dotenv()

DOWNLOADS_DIR = os.getenv('DOWNLOADS_DIR', '/app/downloads')
USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'

def update_task_progress(task_id, status, progress=0.0, filename=None):
    from main import app
    with app.app_context():
        task = DownloadTask.query.get(task_id)
        if task:
            if status: task.status = status
            if progress is not None: task.progress = progress
            if filename: task.filename = filename
            db.session.commit()

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
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1
        )
        
        # Regex to capture percentage from yt-dlp: [download]  12.5% of ...
        progress_re = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
        
        # Try to find filename from output
        filename = None

        while True:
            line = process.stdout.readline()
            if not line:
                break
            
            # Update progress
            match = progress_re.search(line)
            if match:
                progress = float(match.group(1))
                update_task_progress(task_id, progress=progress)
            
            # Capture filename when it starts writing
            if '[download] Destination:' in line:
                filename = line.split('Destination: ')[-1].strip()
                update_task_progress(task_id, filename=filename)

        process.wait()
        if process.returncode == 0:
            update_task_progress(task_id, 'completed', progress=100.0)
        else:
            update_task_progress(task_id, 'error')
            
    except Exception as e:
        print(f"Error downloading {video_id}: {e}")
        update_task_progress(task_id, 'error')

def compress_video(input_filename, preset, task_id, user_id):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    input_path = os.path.join(DOWNLOADS_DIR, input_filename)
    output_filename = f"compressed_{preset}_{input_filename}"
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    
    # QSV Presets
    # Fast: Low bitrate, high speed
    # Balanced: Standard
    # High: High bitrate, slower
    presets = {
        'fast': {'bitrate': '2M', 'preset': 'veryfast'},
        'balanced': {'bitrate': '5M', 'preset': 'medium'},
        'high': {'bitrate': '10M', 'preset': 'slow'}
    }
    
    p = presets.get(preset, presets['balanced'])
    
    # Intel QSV Compression Command
    # -c:v h264_qsv: Use Intel hardware encoder
    # -b:v: Set target bitrate
    cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-c:v', 'h264_qsv',
        '-b:v', p['bitrate'],
        '-preset', p['preset'],
        '-c:a', 'copy', # copy audio to avoid re-encoding
        output_path
    ]
    
    update_task_progress(task_id, 'processing')
    
    try:
        # Note: FFmpeg progress parsing is more complex. 
        # For simplicity in this MVP, we'll mark as processing and then completed.
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        update_task_progress(task_id, 'completed', progress=100.0, filename=output_filename)
    except Exception as e:
        print(f"Error compressing {input_filename}: {e}")
        update_task_progress(task_id, 'error')

def start_download_async(url, video_id, task_id):
    thread = threading.Thread(target=download_vod, args=(url, video_id, task_id))
    thread.start()
    return thread

def start_compress_async(input_filename, preset, task_id, user_id):
    thread = threading.Thread(target=compress_video, args=(input_filename, preset, task_id, user_id))
    thread.start()
    return thread
