import os
import requests
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
from models import db, Favorite, DownloadTask, MonitoredChannel, ChatMessage
from utils.system import get_twitch_token

social_bp = Blueprint('social', __name__)

@social_bp.route('/api/videos', methods=['POST'])
@login_required
def list_videos():
    channel_name = request.json.get('channel')
    if not channel_name:
        return jsonify({'error': 'Channel name is required'}), 400
    
    try:
        token = get_twitch_token()
        headers = {
            'Client-ID': os.getenv('TWITCH_CLIENT_ID'),
            'Authorization': f'Bearer {token}'
        }
        
        user_res = requests.get(f'https://api.twitch.tv/helix/users?login={channel_name}', headers=headers)
        user_res.raise_for_status()
        user_data = user_res.json().get('data')
        if not user_data:
            return jsonify({'error': 'Channel not found'}), 404
        
        user_id = user_data[0]['id']
        
        vod_res = requests.get(f'https://api.twitch.tv/helix/videos?user_id={user_id}', headers=headers)
        vod_res.raise_for_status()
        videos = vod_res.json().get('data', [])
        
        return jsonify({'channel_info': user_data[0], 'videos': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@social_bp.route('/api/favorites', methods=['GET', 'POST'])
@login_required
def manage_favorites():
    if request.method == 'POST':
        data = request.json
        channel = data.get('channel')
        if not channel:
            return jsonify({'error': 'Channel name required'}), 400
        
        fav = Favorite.query.filter_by(user_id=current_user.id, channel_name=channel).first()
        if fav:
            db.session.delete(fav)
            db.session.commit()
            return jsonify({'status': 'removed'})
        else:
            new_fav = Favorite(user_id=current_user.id, channel_name=channel)
            db.session.add(new_fav)
            db.session.commit()
            return jsonify({'status': 'added'})
            
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    enriched_favs = []
    try:
        token = get_twitch_token()
        headers = {
            'Client-ID': os.getenv('TWITCH_CLIENT_ID'),
            'Authorization': f'Bearer {token}'
        }
        
        names = [f.channel_name for f in favs]
        if names:
            user_map = {}
            chunk_size = 50
            for i in range(0, len(names), chunk_size):
                chunk = names[i:i + chunk_size]
                try:
                    login_params = '&'.join([f'login={name}' for name in chunk])
                    user_res = requests.get(
                        f"https://api.twitch.tv/helix/users?{login_params}", 
                        headers=headers,
                        timeout=10
                    )
                    user_res.raise_for_status()
                    users_data = user_res.json().get('data', [])
                    for u in users_data:
                        user_map[u['login'].lower()] = u
                except Exception as e:
                    from flask import current_app
                    current_app.logger.error(f"Error fetching chunk {i//chunk_size + 1}: {e}")
            
            for f in favs:
                u_info = user_map.get(f.channel_name.lower(), {})
                enriched_favs.append({
                    'channel_name': f.channel_name,
                    'profile_image_url': u_info.get('profile_image_url', ''),
                    'description': u_info.get('description', '')
                })
        else:
            enriched_favs = []
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error enriching favorites: {e}")
        enriched_favs = [{'channel_name': f.channel_name, 'profile_image_url': ''} for f in favs]
    
    return jsonify({'favorites': enriched_favs})

@social_bp.route('/api/monitored', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def manage_monitored():
    if request.method == 'GET':
        channels = MonitoredChannel.query.filter_by(user_id=current_user.id).all()
        return jsonify({
            'channels': [{
                'id': c.id,
                'channel_name': c.channel_name,
                'enabled': c.enabled,
                'auto_compress': c.auto_compress,
                'compression_presets': c.compression_presets,
                'target_codec': c.target_codec,
                'delete_original': c.delete_original
            } for c in channels]
        })
    
    if request.method == 'POST':
        data = request.json
        channel_name = data.get('channel_name')
        if not channel_name:
            return jsonify({'error': 'Channel name is required'}), 400
        
        if MonitoredChannel.query.filter_by(user_id=current_user.id, channel_name=channel_name).first():
            return jsonify({'error': 'Channel already monitored'}), 400
            
        new_channel = MonitoredChannel(
            user_id=current_user.id,
            channel_name=channel_name,
            enabled=data.get('enabled', True),
            auto_compress=data.get('auto_compress', False),
            compression_presets=data.get('compression_presets', ''),
            target_codec=data.get('target_codec', 'AV1'),
            delete_original=data.get('delete_original', False)
        )
        db.session.add(new_channel)
        db.session.commit()
        return jsonify({'message': 'Channel added to monitoring list', 'id': new_channel.id})
    
    if request.method == 'PUT':
        data = request.json
        channel_id = data.get('id')
        if not channel_id:
            return jsonify({'error': 'Channel ID required'}), 400
            
        channel = MonitoredChannel.query.filter_by(id=channel_id, user_id=current_user.id).first()
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404
            
        channel.enabled = data.get('enabled', channel.enabled)
        channel.auto_compress = data.get('auto_compress', channel.auto_compress)
        channel.compression_presets = data.get('compression_presets', channel.compression_presets)
        channel.target_codec = data.get('target_codec', channel.target_codec)
        channel.delete_original = data.get('delete_original', channel.delete_original)
        db.session.commit()
        return jsonify({'message': 'Monitoring settings updated'})
    
    if request.method == 'DELETE':
        data = request.json
        channel_id = data.get('id')
        if not channel_id:
            return jsonify({'error': 'Channel ID required'}), 400
            
        channel = MonitoredChannel.query.filter_by(id=channel_id, user_id=current_user.id).first()
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404
            
        db.session.delete(channel)
        db.session.commit()
        return jsonify({'message': 'Channel removed from monitoring list'})
    
    return jsonify({'error': 'Method not allowed'}), 405

@social_bp.route('/api/download/chat/<video_id>', methods=['POST'])
@login_required
def download_chat_route(video_id):
    clean_id = video_id[1:] if video_id.startswith('v') else video_id
    task = DownloadTask.query.filter_by(video_id=clean_id).first()
    if not task:
        return jsonify({'error': 'Video not found'}), 404
    
    from chat_manager import start_chat_download_async
    start_chat_download_async(clean_id, task.id)
    return jsonify({'message': 'Chat download started in background'})

@social_bp.route('/api/chat/<video_id>')
@login_required
def get_chat(video_id):
    from flask import current_app
    current_app.logger.info(f"Chat API requested for video_id: {video_id}")
    clean_id = video_id[1:] if video_id.startswith('v') else video_id
    
    task = DownloadTask.query.filter_by(video_id=clean_id).first()
    if not task and ('.' in clean_id or len(clean_id) > 20):
        safe_filename = os.path.basename(clean_id)
        task = DownloadTask.query.filter_by(filename=safe_filename).first()
        
    if not task:
        return jsonify({'error': 'Video not found in database'}), 404
    
    messages = ChatMessage.query.filter_by(task_id=task.id).order_by(ChatMessage.time_in_seconds).all()
    
    if not messages:
        try:
            from chat_manager import download_chat_sync
            vid_id = task.video_id if task.video_id else clean_id
            chat_data = download_chat_sync(vid_id, task.id)
            return jsonify([{
                'username': m['username'],
                'message': m['message'],
                'time': m['time']
            } for m in chat_data])
        except Exception as e:
            current_app.logger.error(f"Synchronous chat download failed: {e}")
            return jsonify({'error': 'Failed to download chat synchronously', 'details': str(e)}), 500
    
    return jsonify([{
        'username': m.username,
        'message': m.message,
        'time': m.time_in_seconds
    } for m in messages])

@social_bp.route('/api/chat/export/<video_id>')
@login_required
def export_chat(video_id):
    clean_id = video_id[1:] if video_id.startswith('v') else video_id
    task = DownloadTask.query.filter_by(video_id=clean_id).first()
    if not task:
        return jsonify({'error': 'Video not found'}), 404
    
    messages = ChatMessage.query.filter_by(task_id=task.id).order_by(ChatMessage.time_in_seconds).all()
    data = [{
        'username': m.username,
        'message': m.message,
        'time_in_seconds': m.time_in_seconds,
        'timestamp': m.timestamp.isoformat() if m.timestamp else None
    } for m in messages]
    
    import json
    return Response(json.dumps(data, indent=2), mimetype='application/json', 
                    headers={'Content-Disposition': f'attachment; filename=chat_{video_id}.json'})
