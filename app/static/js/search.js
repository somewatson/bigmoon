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
                <div>
                    <h2>${channel}</h2>
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
                .replace('%{width}', '1280')
                .replace('%{height}', '720');

            const durationStr = video.duration || "Unknown";

            card.innerHTML = `
                <img src="${thumbUrl}" alt="thumbnail">
                <div class="duration-badge">${durationStr}</div>
                <div class="video-card-body">
                    <h3>${video.title}</h3>
                    <p>Created: ${new Date(video.created_at).toLocaleDateString()} | Duration: ${durationStr}</p>
                    <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                            <button onclick="downloadVideo('${video.url}', '${video.id}')" style="flex: 1;" data-tooltip="Download this VOD">Download</button>
                            <button onclick="previewVideo('${video.id}')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 0 10px; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>
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

async function previewVideo(identifier) {
    const hostname = window.location.hostname;
    const wrapper = document.getElementById('videoPlayerWrapper');
    const chatContainer = document.getElementById('chatContainer');
    const chatMessages = document.getElementById('chatMessages');
    const downloadChatBtn = document.getElementById('downloadChatBtn');

    let videoPlayer = document.getElementById('videoPlayer');

    if (identifier.includes('.') || identifier.length > 20) {
        if (videoPlayer && videoPlayer.tagName === 'IFRAME') {
            videoPlayer.remove();
        }
        videoPlayer = document.createElement('video');
        videoPlayer.id = 'videoPlayer';
        videoPlayer.controls = true;
        videoPlayer.autoplay = true;
        videoPlayer.style.width = '100%';
        videoPlayer.style.height = '100%';
        videoPlayer.src = `/api/preview/${identifier}`;
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
    } else if (identifier.includes('.') || identifier.length > 20) {
        chatIdentifier = null;
    }

    try {
        if (!chatIdentifier) {
            chatContainer.style.display = 'none';
            return;
        }
        const response = await fetch(`/api/chat/${chatIdentifier}`);
        const data = await response.json();
        
        if (data.error || data.length === 0) {
            chatContainer.style.display = 'none';
        } else {
            chatContainer.style.display = 'block';
            chatMessages.innerHTML = data.map(m => `
                <div class="chat-message" style="margin-bottom: 4px; font-size: 0.85rem;">
                    <span style="color: var(--primary); font-weight: bold;">${m.username}:</span>
                    <span>${m.message}</span>
                    <span style="color: var(--text-dim); font-size: 0.7rem; float: right;">${Math.floor(m.time)}s</span>
                </div>
            `).join('');
            
            downloadChatBtn.onclick = () => {
                window.open(`/api/chat/export/${chatIdentifier}`, '_blank');
            };
        }
    } catch (e) {
        console.error('Failed to load chat:', e);
        chatContainer.style.display = 'none';
    }
}

function closePreview() {
    document.getElementById('previewModal').classList.remove('active');
    const wrapper = document.getElementById('videoPlayerWrapper');
    if (wrapper) wrapper.innerHTML = '';
}

window.searchVideos = searchVideos;
window.toggleFavorite = toggleFavorite;
window.downloadVideo = downloadVideo;
window.previewVideo = previewVideo;
window.closePreview = closePreview;
