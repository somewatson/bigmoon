// Define functions globally to ensure they are accessible from inline onclick attributes
window.currentTab = '{{ current_tab }}';
if (!window.currentTab || window.currentTab === 'None') {
    window.currentTab = localStorage.getItem('bigmoon_current_tab') || 'search';
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const btn = document.querySelector('.sidebar-toggle');
    sidebar.classList.toggle('collapsed');
    btn.textContent = sidebar.classList.contains('collapsed') ? '▶' : '◀';
}
window.toggleSidebar = toggleSidebar;

async function previewVideo(filename, type = 'file') {
    const modal = document.getElementById('previewModal');
    const wrapper = document.getElementById('videoPlayerWrapper');
    const chatContainer = document.getElementById('chatContainer');
    const chatMessages = document.getElementById('chatMessages');
    const downloadChatBtn = document.getElementById('downloadChatBtn');
    
    modal.classList.add('active');
    
    let videoPlayer = document.getElementById('videoPlayer');
    if (!videoPlayer) {
        videoPlayer = document.createElement(type === 'file' ? 'video' : 'iframe');
        videoPlayer.id = 'videoPlayer';
        wrapper.appendChild(videoPlayer);
    }

    if (type === 'file') {
        if (videoPlayer.tagName === 'IFRAME') {
            videoPlayer.remove();
            videoPlayer = document.createElement('video');
            videoPlayer.id = 'videoPlayer';
            wrapper.appendChild(videoPlayer);
        }
        videoPlayer.controls = true;
        videoPlayer.autoplay = true;
        videoPlayer.style.position = 'absolute';
        videoPlayer.style.top = '0';
        videoPlayer.style.left = '0';
        videoPlayer.style.width = '100%';
        videoPlayer.style.height = '100%';
        videoPlayer.src = `/api/preview/${encodeURIComponent(filename)}`;
    } else {
        if (videoPlayer.tagName === 'VIDEO') {
            videoPlayer.remove();
            videoPlayer = document.createElement('iframe');
            videoPlayer.id = 'videoPlayer';
            wrapper.appendChild(videoPlayer);
        }
        const hostname = window.location.hostname;
        videoPlayer.src = `https://player.twitch.tv/?video=${filename}&parent=${hostname}`;
        videoPlayer.style.width = '100%';
        videoPlayer.style.height = '100%';
        videoPlayer.style.border = 'none';
        videoPlayer.allowFullscreen = true;
    }
    
    // Extract video_id from filename if possible (assuming [id] pattern)
    const match = filename.match(/\[([a-zA-Z0-9]+)\]/);
    const videoId = match ? match[1] : (type === 'vod' ? filename : null);
    
    if (videoId) {
        chatContainer.style.display = 'block';
        chatMessages.innerHTML = 'Loading chat...';
        downloadChatBtn.onclick = () => {
            window.location.href = `/api/chat/export/${videoId}`;
        };
        
        try {
            const response = await fetch(`/api/chat/${videoId}`);
            const data = await response.json();
            
            if (data.error) {
                chatMessages.innerHTML = `<div style="color: var(--text-dim);">${data.error}</div>`;
            } else if (data.length === 0) {
                chatMessages.innerHTML = `<div style="color: var(--text-dim);">No chat messages found.</div>`;
            } else {
                chatMessages.innerHTML = data.map(m => `
                    <div style="font-size: 0.85rem; line-height: 1.4; margin-bottom: 4px;">
                        <span style="color: #aaa; font-weight: bold;">[${Math.floor(m.time)}s] ${m.username}:</span> 
                        <span style="color: #eee;">${m.message}</span>
                    </div>
                `).join('');
            }
        } catch (e) {
            chatMessages.innerHTML = `<div style="color: var(--error);">Failed to load chat.</div>`;
        }
    } else {
        chatContainer.style.display = 'none';
    }
}
window.previewVideo = previewVideo;

async function viewChat(videoId) {
    const modal = document.getElementById('previewModal');
    const video = document.getElementById('videoPlayer');
    const chatContainer = document.getElementById('chatContainer');
    const chatMessages = document.getElementById('chatMessages');
    const downloadChatBtn = document.getElementById('downloadChatBtn');
    
    modal.classList.add('active');
    video.src = ''; // No video if just viewing chat
    
    chatContainer.style.display = 'block';
    chatMessages.innerHTML = 'Loading chat...';
    downloadChatBtn.onclick = () => {
        window.location.href = `/api/chat/export/${videoId}`;
    };
    
    try {
        const response = await fetch(`/api/chat/${videoId}`);
        const data = await response.json();
        
        if (data.error) {
            chatMessages.innerHTML = `<div style="color: var(--text-dim);">${data.error}</div>`;
        } else if (data.length === 0) {
            chatMessages.innerHTML = `<div style="color: var(--text-dim);">No chat messages found.</div>`;
        } else {
            chatMessages.innerHTML = data.map(m => `
                <div style="font-size: 0.85rem; line-height: 1.4; margin-bottom: 4px;">
                    <span style="color: #aaa; font-weight: bold;">[${Math.floor(m.time)}s] ${m.username}:</span> 
                    <span style="color: #eee;">${m.message}</span>
                </div>
            `).join('');
        }
    } catch (e) {
        chatMessages.innerHTML = `<div style="color: var(--error);">Failed to load chat.</div>`;
    }
}
window.viewChat = viewChat;

function closePreview() {
    const modal = document.getElementById('previewModal');
    const video = document.getElementById('videoPlayer');
    modal.classList.remove('active');
    video.pause();
    video.src = '';
}
window.closePreview = closePreview;

function toggleAdminMenu() {

    const submenu = document.getElementById('adminSubmenu');
    if (!submenu) return;
    submenu.classList.toggle('active');
}
window.toggleAdminMenu = toggleAdminMenu;

// Polling for tasks
setInterval(() => {
    if (window.currentTab === 'tasks') {
        loadTasks();
    }
}, 3000);

window.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const tabFromUrl = urlParams.get('tab');
    const initialTab = tabFromUrl || window.currentTab || localStorage.getItem('bigmoon_current_tab') || 'search';
    showTab(initialTab);

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            const tabId = item.getAttribute('data-tab');
            if (tabId) {
                e.preventDefault();
                showTab(tabId);
            } else if (item.id === 'nav-admin') {
                window.location.href = '/admin';
            }
        });
    });
});
