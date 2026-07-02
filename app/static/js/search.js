async function searchVideos() {
    const channel = document.getElementById('channelInput').value;
    const grid = document.getElementById('videoGrid');
    const channelInfo = document.getElementById('channelInfo');
    if (!channel) return;
    
    grid.innerHTML = '';
    channelInfo.innerHTML = '<p>Searching Twitch...</p>';
    try {
        const response = await apiFetch('/api/videos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel })
        });
        const data = await response.json();
        if (data.error) throw new Error(data.error);
        
        const profileImg = data.channel_info?.profile_image_url || `https://api.dicebear.com/7.x/initials/svg?seed=${channel}`;
        channelInfo.innerHTML = `
            <div class="channel-card">
                <img src="${profileImg}" alt="avatar">
                <div style="flex: 1;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <h2 style="margin: 0;">${channel}</h2>
                        <a href="https://twitch.tv/${channel}" target="_blank" style="font-size: 0.85rem; text-decoration: none; color: var(--primary); font-weight: bold; padding: 2px 8px; border: 1px solid var(--primary); border-radius: 4px; transition: 0.2s;" onmouseover="this.style.background='var(--primary)'; this.style.color='white'" onmouseout="this.style.background='transparent'; this.style.color='var(--primary)';" data-tooltip="Visit channel on Twitch">Visit Profile</a>
                    </div>
                    <p class="channel-description">${data.channel_info?.description || 'No description available.'}</p>
                </div>
                <button class="fav-btn" onclick="toggleFavorite('${channel}')" data-tooltip="Add to Favorites">❤️</button>
            </div>
        `;
        
        grid.innerHTML = '';
        data.videos.forEach(video => {
            const card = document.createElement('div');
            card.className = 'video-card';
            
            const thumbUrl = video.thumbnail_url
                ? video.thumbnail_url.replace('%{width}', '1280').replace('%{height}', '720')
                : '';
        
            const durationStr = video.duration || "Unknown";
            const isRecent = (Date.now() - new Date(video.created_at).getTime()) < 3600000; // Last 1 hour
        
            card.innerHTML = `
                <div style="position: relative; width: 100%; height: 160px; overflow: hidden; background: #1a1a1a;">
                    <img src="${thumbUrl}" alt="thumbnail" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <div class="thumb-fallback" style="display: none; width: 100%; height: 100%; align-items: center; justify-content: center; color: var(--primary); font-weight: bold; font-size: 1.2rem; text-transform: uppercase; animation: glow 2s infinite alternate;">LIVE</div>
                    ${isRecent ? `<span style="position: absolute; top: 10px; left: 10px; background: var(--error); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase; animation: pulse 1.5s infinite; z-index: 10;">Processing</span>` : ''}
                    <div class="duration-badge">${durationStr}</div>
                </div>
                <div class="video-card-body">
                    <h3>${video.title}</h3>
                    <p>Created: ${new Date(video.created_at).toLocaleDateString()} | Duration: ${durationStr}</p>
                    <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                            <button onclick="downloadVideo('${video.url}', '${video.id}')" style="flex: 1;" data-tooltip="Download this VOD">Download</button>
                            <button onclick="previewVideo('${video.id}', 'vod')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 0 10px; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>
                            <a href="${video.url}" target="_blank" style="text-align: center; display: flex; align-items: center; justify-content: center; background: #444; color: white; text-decoration: none; border-radius: 6px; font-size: 0.8rem; font-weight: bold; padding: 0 10px; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Open on Twitch">View VOD</a>
                        </div>
                    </div>
            `;
            grid.appendChild(card);
        });
    } catch (e) {
        channelInfo.innerHTML = `<p style="color: var(--error)">${e.message}</p>`;
    }
}

function quickSearch(channel) {
    document.getElementById('channelInput').value = channel;
    searchVideos();
}


async function toggleFavorite(channel) {
    try {
        await apiFetch('/api/favorites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel })
        });
        if(window.currentTab === 'favorites') loadFavorites();
        searchVideos();
    } catch (e) {
        showToast('Connection error. Please try again.', 'error');
    }
}

async function downloadVideo(url, id) {
    try {
        const response = await apiFetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, id })
        });
        const data = await response.json();
        if(data.taskId) window.showTab('tasks');
    } catch (e) {
        showToast('Connection error. Please try again.', 'error');
    }
}

async function previewVideo(identifier, type) {
    const hostname = window.location.hostname;
    const wrapper = document.getElementById('videoPlayerWrapper');
    const chatContainer = document.getElementById('chatContainer');
    const chatMessages = document.getElementById('chatMessages');
    const downloadChatBtn = document.getElementById('downloadChatBtn');

    let videoPlayer = document.getElementById('videoPlayer');

    if (type === 'file') {
        if (videoPlayer && videoPlayer.tagName === 'IFRAME') {
            videoPlayer.remove();
        }
        videoPlayer = document.createElement('video');
        videoPlayer.id = 'videoPlayer';
        videoPlayer.controls = true;
        videoPlayer.autoplay = true;
        videoPlayer.style.position = 'absolute';
        videoPlayer.style.top = '0';
        videoPlayer.style.left = '0';
        videoPlayer.style.width = '100%';
        videoPlayer.style.height = '100%';
        videoPlayer.src = `/api/preview/${encodeURIComponent(identifier)}`;
        
        // Fallback to Twitch player if local file is not found (404)
        videoPlayer.onerror = () => {
            console.log('Local preview failed, falling back to Twitch player');
            videoPlayer.remove();
            // We don't have the original VOD ID here easily if it was just a filename, 
            // but if it's a numeric ID that was mislabeled as 'file', this would work.
            // Since we are now explicit, this fallback is less likely to be needed for VODs.
        };
        
        wrapper.appendChild(videoPlayer);
    } else {
        if (videoPlayer && videoPlayer.tagName === 'VIDEO') {
            videoPlayer.remove();
        }
        videoPlayer = document.createElement('iframe');
        videoPlayer.id = 'videoPlayer';
        videoPlayer.src = `https://player.twitch.tv/?video=${identifier}&parent=${hostname}`;
        videoPlayer.style.width = '100%';
        videoPlayer.style.height = '100%';
        videoPlayer.style.border = 'none';
        videoPlayer.allowFullscreen = true;
        wrapper.appendChild(videoPlayer);
    }
    
    document.getElementById('previewModal').classList.add('active');
    
    let chatIdentifier = identifier;
    const videoIdMatch = identifier.match(/\[(v\d+)\]/);
    if (videoIdMatch) {
        chatIdentifier = videoIdMatch[1];
    } else if (type === 'file' && (identifier.includes('.') || identifier.length > 20)) {
        // Keep the identifier as the filename, the backend will now handle the lookup
        chatIdentifier = identifier;
    }
    
    try {
        if (!chatIdentifier) {
            chatContainer.style.display = 'none';
            return;
        }
        const response = await fetch(`/api/chat/${chatIdentifier}`);
        
        if (response.status === 202) {
            const data = await response.json();
            chatContainer.style.display = 'block';
            chatMessages.innerHTML = `<div style="text-align: center; color: var(--text-dim); padding: 20px;">${data.message}</div>`;
            
            // Poll for chat completion
            const pollInterval = setInterval(async () => {
                const pollRes = await fetch(`/api/chat/${chatIdentifier}`);
                if (pollRes.status === 200) {
                    const pollData = await pollRes.json();
                    if (pollData.length > 0) {
                        clearInterval(pollInterval);
                        renderChatMessages(pollData, chatIdentifier);
                    }
                }
            }, 3000);
            return;
        }

        const data = await response.json();
        
        if (data.error || data.length === 0) {
            chatContainer.style.display = 'none';
        } else {
            renderChatMessages(data, chatIdentifier);
        }
    } catch (e) {
        console.error('Failed to load chat:', e);
        chatContainer.style.display = 'none';
    }
}

function renderChatMessages(data, chatIdentifier) {
    const chatContainer = document.getElementById('chatContainer');
    const chatMessages = document.getElementById('chatMessages');
    const downloadChatBtn = document.getElementById('downloadChatBtn');

    chatContainer.style.display = 'block';
    chatMessages.innerHTML = '';
    chatMessages.innerHTML = data.map((m, idx) => `
        <div class="chat-message" data-time="${m.time}" id="msg-${idx}" style="margin-bottom: 4px; font-size: 0.85rem; cursor: pointer; transition: background 0.2s;" onclick="seekToChatTime(${m.time})">
            <span style="color: var(--primary); font-weight: bold;">${m.username}:</span>
            <span>${m.message}</span>
            <span style="color: var(--text-dim); font-size: 0.7rem; float: right;">${formatTime(m.time)}</span>
        </div>
    `).join('');
    
    downloadChatBtn.onclick = () => {
        window.open(`/api/chat/export/${chatIdentifier}`, '_blank');
    };

    const videoPlayer = document.getElementById('videoPlayer');
    if (videoPlayer && videoPlayer.tagName === 'VIDEO') {
        videoPlayer.ontimeupdate = () => syncChat(videoPlayer.currentTime);
    }
}


function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return h > 0 
        ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
        : `${m}:${s.toString().padStart(2, '0')}`;
}

function seekToChatTime(time) {
    const videoPlayer = document.getElementById('videoPlayer');
    if (videoPlayer && videoPlayer.tagName === 'VIDEO') {
        videoPlayer.currentTime = time;
    } else {
        showToast('Seeking only supported for local video previews', 'info');
    }
}

function syncChat(currentTime) {
    const messages = document.querySelectorAll('.chat-message');
    let closest = null;
    let minDiff = Infinity;

    messages.forEach(msg => {
        const msgTime = parseFloat(msg.dataset.time);
        const diff = Math.abs(currentTime - msgTime);
        if (diff < minDiff) {
            minDiff = diff;
            closest = msg;
        }
    });

    if (closest && minDiff < 2) {
        messages.forEach(m => m.style.background = 'transparent');
        closest.style.background = 'rgba(145, 70, 255, 0.2)';
        closest.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function closePreview() {
    document.getElementById('previewModal').classList.remove('active');
    const wrapper = document.getElementById('videoPlayerWrapper');
    if (wrapper) wrapper.innerHTML = '';
}

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('previewModal');
        if (modal && modal.classList.contains('active')) {
            closePreview();
        }
    }
});

window.searchVideos = searchVideos;
window.toggleFavorite = toggleFavorite;
window.downloadVideo = downloadVideo;
window.previewVideo = previewVideo;
window.closePreview = closePreview;
