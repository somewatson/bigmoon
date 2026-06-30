import os
import math
import requests
import logging

def format_size(size_bytes):
    if size_bytes == 0: return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def calculate_savings(original, current):
    if not isinstance(original, (int, float)) or not isinstance(current, (int, float)):
        return None
    if original <= 0: return None
    saved = original - current
    percent = (saved / original) * 100
    return f"{format_size(saved)} ({round(percent, 1)}%)"

def get_twitch_token():
    client_id = os.getenv('TWITCH_CLIENT_ID')
    client_secret = os.getenv('TWITCH_CLIENT_SECRET')
    url = f'https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials'
    response = requests.post(url)
    response.raise_for_status()
    return response.json()['access_token']

def cleanup_temp_files():
    downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
    try:
        files = os.listdir(downloads_dir)
        temp_files = [f for f in files if f.endswith('.temp.mp4') or f.endswith('.temp')]
        for f in temp_files:
            os.remove(os.path.join(downloads_dir, f))
        
        # Also clean up orphaned thumbnails
        thumb_dir = os.path.join(downloads_dir, '.thumbnails')
        if os.path.exists(thumb_dir):
            thumb_files = os.listdir(thumb_dir)
            actual_files = set(files)
            for tf in thumb_files:
                # If the thumbnail is for a file that no longer exists, delete it
                original_filename = tf.replace('.jpg', '')
                if original_filename not in actual_files:
                    os.remove(os.path.join(thumb_dir, tf))
                    
        if temp_files:
            logging.info(f"Cleaned up {len(temp_files)} temporary files from {downloads_dir}")
    except Exception as e:
        logging.error(f"Error cleaning up temp files: {e}")
