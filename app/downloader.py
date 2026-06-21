import os
import subprocess
import threading
from dotenv import load_dotenv

load_dotenv()

DOWNLOADS_DIR = os.getenv('DOWNLOADS_DIR', '/app/downloads')
USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'

def download_vod(url, video_id):
    # Ensure downloads directory exists
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    
    # yt-dlp arguments
    # --merge-output-format mp4 for compatibility
    # --ffmpeg-location /usr/bin/ffmpeg
    cmd = [
        'yt-dlp',
        '-o', f'{DOWNLOADS_DIR}/%(title)s [%(id)s].%(ext)s',
        url
    ]
    
    if USE_GPU:
        # Use Intel QuickSync for merging/transcoding if specified
        # h264_qsv is the Intel QSV encoder
        # We pass this via post-processor-args to ffmpeg
        cmd.extend([
            '--postprocessor-args', 
            'ffmpeg:-c:v h264_qsv'
        ])
    
    try:
        print(f"Starting download for {video_id}...")
        subprocess.run(cmd, check=True)
        print(f"Finished download for {video_id}")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading {video_id}: {e}")
    except Exception as e:
        print(f"Unexpected error downloading {video_id}: {e}")

def start_download_async(url, video_id):
    thread = threading.Thread(target=download_vod, args=(url, video_id))
    thread.start()
    return thread
