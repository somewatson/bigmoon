import os
import threading
import traceback
import json
from datetime import datetime
from models import db, DownloadTask, ChatMessage

def download_chat_sync(video_id, task_id):
    """Synchronously downloads chat and saves it to the database and a JSON file."""
    try:
        from chat_downloader import ChatDownloader
        
        # Mark as downloading immediately to prevent duplicate triggers
        task = DownloadTask.query.get(task_id)
        if task:
            task.chat_status = 'downloading'
            db.session.commit()

        downloader = ChatDownloader.get_twitch_chat(video_id)
        chat_data = []
        for message in downloader.get_chat_entries():
            chat_msg = ChatMessage(
                task_id=task_id,
                username=message.get('username'),
                message=message.get('message'),
                time_in_seconds=message.get('timestamp'),
                timestamp=datetime.fromtimestamp(message.get('timestamp', 0)) if message.get('timestamp') else None
            )
            db.session.add(chat_msg)
            chat_data.append({
                'username': message.get('username'),
                'message': message.get('message'),
                'time': message.get('timestamp'),
                'timestamp': message.get('timestamp')
            })
            # Commit in batches to improve performance
            if len(db.session.new) >= 100:
                db.session.commit()
        
        db.session.commit()

        # Save to chat.json file
        downloads_dir = os.getenv('DOWNLOADS_DIR', '/app/downloads')
        chat_filename = f"chat_{video_id}.json"
        chat_path = os.path.join(downloads_dir, chat_filename)
        with open(chat_path, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=2)
        
        task = DownloadTask.query.get(task_id)
        if task:
            task.chat_json_path = chat_path
            task.chat_status = 'completed'
            db.session.commit()
            
        return chat_data

    except Exception as e:
        print(f"Error downloading chat for {video_id}: {e}")
        print(traceback.format_exc())
        task = DownloadTask.query.get(task_id)
        if task:
            task.chat_status = 'error'
            db.session.commit()
        raise e

def start_chat_download_async(video_id, task_id):
    def run_download():
        try:
            from main import app
            with app.app_context():
                download_chat_sync(video_id, task_id)
        except Exception:
            pass
    
    thread = threading.Thread(target=run_download, daemon=True)
    thread.start()
    return thread
