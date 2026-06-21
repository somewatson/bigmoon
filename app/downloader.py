import os
import subprocess
import threading
import re
import traceback
from dotenv import load_dotenv
from models import db, DownloadTask

load_dotenv()

DOWNLOADS_DIR = os.getenv('DOWNLOADS_DIR', '/app/downloads')
USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'

def update_task_progress(task_id, status=None, progress=None, filename=None, error_log=None):
    from main import app
    with app.app_context():
        try:
            task = DownloadTask.query.get(task_id)
            if task:
                if status is not None: task.status = status
                if progress is not None: task.progress = progress
                if filename is not None: task.filename = filename
                if error_log is not None: task.error_log = error_log
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
        
        # Even if returncode != 0, check if the file actually exists
        success = process.returncode == 0
        if not success and filename and os.path.exists(filename):
            success = True
            
        if success:
            update_task_progress(task_id, 'completed', progress=100.0)
            cleanup_temp_files()
        else:
            update_task_progress(task_id, 'error', error_log="yt-dlp process failed and no output file found.")
            cleanup_temp_files()
            
    except Exception as e:
        print(f"Error downloading {video_id}: {e}")
        print(traceback.format_exc())
        update_task_progress(task_id, 'error')
        cleanup_temp_files()

def compress_video(input_filename, preset, task_id, user_id, codec='H.264'):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    input_path = os.path.join(DOWNLOADS_DIR, input_filename)
    output_filename = f"compressed_{codec}_{preset}_{input_filename}"
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    
    presets = {
        'fast': {
            'bitrate': '2M', 
            'h264_sw': 'veryfast', 'h264_hw': 'veryfast',
            'h265_sw': 'veryfast', 'h265_hw': 'veryfast',
            'av1_sw': '8', 'av1_hw': 'veryfast'
        },
        'balanced': {
            'bitrate': '5M', 
            'h264_sw': 'medium', 'h264_hw': 'balanced',
            'h265_sw': 'medium', 'h265_hw': 'balanced',
            'av1_sw': '6', 'av1_hw': 'fast'
        },
        'high': {
            'bitrate': '10M', 
            'h264_sw': 'slow', 'h264_hw': 'quality',
            'h265_sw': 'slow', 'h265_hw': 'quality',
            'av1_sw': '4', 'av1_hw': 'quality'
        }
    }
    
    p = presets.get(preset, presets['balanced'])
    
    codec_map = {
        'H.264': {'hw': 'h264_qsv', 'sw': 'libx264', 'prefix': 'h264'},
        'H.265': {'hw': 'hevc_qsv', 'sw': 'libx265', 'prefix': 'h265'},
        'AV1': {'hw': 'av1_qsv', 'sw': 'libsvtav1', 'prefix': 'av1'},
        'x264': {'hw': None, 'sw': 'libx264', 'prefix': 'h264'}
    }
    
    mapping = codec_map.get(codec, codec_map['H.264'])
    encoders = []
    if mapping['hw']:
        encoders.append(mapping['hw'])
    encoders.append(mapping['sw'])
    
    last_error = ""

    for encoder in encoders:
        # Determine which preset to use based on encoder and hardware/software
        prefix = mapping['prefix']
        is_hw = 'qsv' in encoder
        preset_key = f"{prefix}_{'hw' if is_hw else 'sw'}"
        current_preset = p.get(preset_key, 'medium')
        
        cmd = [
            'ffmpeg',
            '-y',
            '-i', input_path,
            '-c:v', encoder,
            '-b:v', p['bitrate'],
            '-preset', current_preset,
            '-c:a', 'copy',
            output_path
        ]
        
        update_task_progress(task_id, 'processing')
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            update_task_progress(task_id, 'completed', progress=100.0, filename=output_filename)
            return
        except subprocess.CalledProcessError as e:
            last_error = e.stderr
            print(f"FFmpeg encoder {encoder} failed: {e.stderr}")
            continue

    print(f"All encoders failed for {input_filename}. Last error: {last_error}")
    update_task_progress(task_id, 'error', error_log=last_error)

def start_download_async(url, video_id, task_id):
    thread = threading.Thread(target=download_vod, args=(url, video_id, task_id))
    thread.start()
    return thread

def start_compress_async(input_filename, preset, task_id, user_id, codec='H.264'):
    thread = threading.Thread(target=compress_video, args=(input_filename, preset, task_id, user_id, codec))
    thread.start()
    return thread
