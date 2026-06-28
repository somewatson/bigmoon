// Define functions globally to ensure they are accessible from inline onclick attributes
window.currentTab = '{{ current_tab }}';
if (!window.currentTab || window.currentTab === 'None') {
    window.currentTab = localStorage.getItem('bigmoon_current_tab') || 'search';
}
let apiRetryCount = 0;

async function apiFetch(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

    options.signal = controller.signal;

    try {
        const response = await fetch(url, options);
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        apiRetryCount = 0;
        updateConnectionStatus(true);
        return response;
    } catch (e) {
        clearTimeout(timeoutId);
        updateConnectionStatus(false);
        throw e;
    }
}

function updateConnectionStatus(online) {
    const status = document.getElementById('connection-status');
    if (online) {
        status.textContent = 'Connected';
        status.className = 'status-online';
    } else {
        status.textContent = 'Disconnected';
        status.className = 'status-offline';
    }
}

window.showTab = function(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    
    const tab = document.getElementById('tab-' + tabId);
    if(tab) {
        tab.classList.add('active');
    }
    window.currentTab = tabId;
    localStorage.setItem('bigmoon_current_tab', tabId);
    
    // Update URL state without refreshing
    const url = new URL(window.location);
    url.searchParams.set('tab', tabId);
    window.history.pushState({ tab: tabId }, '', url);

    // Sync sidebar highlight
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-tab') === tabId) {
            item.classList.add('active');
        }
    });
    
    if(tabId === 'favorites') loadFavorites();

    if(tabId === 'automation') {
        loadMonitored();
        populateFavAutomationGrid();
    }
    if(tabId === 'library') loadLibrary();
    if(tabId === 'compress') loadFiles();
    if(tabId === 'tasks') loadTasks();
    
    // Sync sidebar highlight
    if (window.showTabGlobal) {
        window.showTabGlobal(tabId);
    }
}

function toggleFavDropdown() {
    // This function is no longer needed as the dropdown was removed.
}

async function populateFavDropdown() {
    // This function is no longer needed as the dropdown was removed.
}


async function populateFavAutomationGrid() {
    const grid = document.getElementById('favAutomationGrid');
    try {
        const response = await fetch('/api/favorites');
        const data = await response.json();
        grid.innerHTML = '';
        
        if (data.favorites.length === 0) {
            grid.innerHTML = '<p style="color: var(--text-dim); font-size: 0.85rem;">No favorites available to add.</p>';
            return;
        }
        
        data.favorites.forEach(fav => {
            const channel = fav.channel_name;
            const card = document.createElement('div');
            card.className = 'fav-mini-card';
            
            const thumbUrl = fav.profile_image_url || `https://api.dicebear.com/7.x/initials/svg?seed=${channel}`;
            
            card.innerHTML = `
                <img src="${thumbUrl}" alt="avatar" onerror="this.src='https://api.dicebear.com/7.x/initials/svg?seed=${channel}'">
                <div class="fav-card-info" style="flex: 1; display: flex; flex-direction: column; gap: 2px; text-align: left; overflow: hidden;">
                    <span class="fav-card-name" style="font-size: 0.9rem; font-weight: bold; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${channel}</span>
                    <p class="fav-card-description" style="font-size: 0.75rem; color: var(--text-dim); margin: 0; line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden;">${fav.description || 'No description available.'}</p>
                </div>
            `;
            card.onclick = (e) => addFavToAutomation(channel, e);
            grid.appendChild(card);
        });
    } catch (e) {
        console.error('Failed to populate fav automation grid:', e);
        grid.innerHTML = '<p style="color: var(--error); font-size: 0.85rem;">Error loading favorites.</p>';
    }
}

async function selectFavForAutomation(channel) {
    document.getElementById('autoChannelInput').value = channel;
    toggleFavDropdown();
    await addMonitoredChannel();
}

// Close dropdown when clicking outside
window.addEventListener('click', (e) => {
    if (!e.target.closest('.fav-dropdown-container')) {
        const dropdown = document.getElementById('favAutomationDropdown');
        if (dropdown) dropdown.classList.remove('active');
    }
});


window.addEventListener('DOMContentLoaded', () => {
    // Try to get tab from URL first, then from variable, then from localStorage
    const urlParams = new URLSearchParams(window.location.search);
    const tabFromUrl = urlParams.get('tab');
    const initialTab = tabFromUrl || window.currentTab || localStorage.getItem('bigmoon_current_tab') || 'search';
    showTab(initialTab);

    // Intercept sidebar clicks for hybrid navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            const tabId = item.getAttribute('data-tab');
            if (tabId) {
                e.preventDefault();
                showTab(tabId);
            } else if (item.id === 'nav-admin') {
                // Redirect to admin dashboard if Admin is clicked and it's a link
                // But if it only toggles the menu, we handle it via toggleAdminMenu
                // The requirement says "Go to Admin page when I click Admin"
                window.location.href = '/admin';
            }
        });
    });
});

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


// Simplified favorite check to avoid async in template string
function isFavoriteSync(channel) {
    // This is a hack because we can't await in template strings easily.
    // In a real app, we'd store favorites in a local JS object.
    return ''; 
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

async function previewVideo(videoId) {
    const hostname = window.location.hostname;
    const videoPlayer = document.getElementById('videoPlayer');
    const chatContainer = document.getElementById('chatContainer');
    const chatMessages = document.getElementById('chatMessages');
    const downloadChatBtn = document.getElementById('downloadChatBtn');

    videoPlayer.src = `https://player.twitch.tv/?video=${videoId}&parent=${hostname}`;
    // Note: Twitch player is an iframe, so we can't easily sync it with a custom HTML video element.
    // However, the task asks for a chat overlay/sidebar and sync with playback.
    // Since we are using the Twitch iframe, we'll provide the chat below it.
    
    document.getElementById('previewModal').classList.add('active');
    
    // Load Chat
    try {
        const response = await fetch(`/api/chat/${videoId}`);
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
                window.open(`/api/chat/export/${videoId}`, '_blank');
            };
        }
    } catch (e) {
        console.error('Failed to load chat:', e);
        chatContainer.style.display = 'none';
    }
}

function closePreview() {
    document.getElementById('previewModal').classList.remove('active');
    document.getElementById('previewContainer').innerHTML = '';
}

async function viewTaskLogs(taskId) {
    const modal = document.getElementById('logModal');
    const container = document.getElementById('logContainer');
    const badgeEl = document.getElementById('logEncoderBadge');
    modal.classList.add('active');
    container.innerHTML = 'Loading logs...';
    badgeEl.innerHTML = '';
    
    window.activeLogTaskId = taskId;
    
    // Always start polling when logs are viewed to ensure they stay updated
    if (window.logPollingInterval) clearInterval(window.logPollingInterval);
    window.logPollingInterval = setInterval(() => fetchLogs(taskId), 2000);
    
    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();
        const task = data.tasks.find(t => t.id === taskId);
        
        if (task) {
            if (task.encoder_type) {
                badgeEl.innerHTML = `<span class="badge ${task.encoder_type === 'HW' ? 'badge-hw' : 'badge-sw'}">${task.encoder_type}</span>`;
            }
            updateLiveBadge(task.status === 'downloading' || task.status === 'processing');
        }
    } catch (e) {
        console.error('Error checking task status for badge:', e);
    }
    
    await fetchLogs(taskId);
}

function updateLiveBadge(isLive) {
    const header = document.querySelector('.log-header');
    const existing = header.querySelector('.badge-live');
    if (existing) existing.remove();
    
    if (isLive) {
        const badge = document.createElement('span');
        badge.className = 'badge badge-live';
        badge.textContent = 'LIVE';
        header.prepend(badge);
    }
}

async function fetchLogs(taskId) {
    if (window.activeLogTaskId !== taskId) return;
    try {
        // 1. Update Metrics
        const metricsRes = await fetch('/api/system/metrics');
        const metricsData = await metricsRes.json();
        if (!metricsData.error) {
            updateMetricBar('cpu', metricsData.cpu);
            updateMetricBar('mem', metricsData.memory);
        }

        // 2. Update Logs
        const response = await fetch(`/api/tasks/${taskId}/logs`);
        const data = await response.json();
        if (data.logs) {
            const lines = data.logs.split('\n');
            const formattedLogs = lines.map(line => {
                if (line.startsWith('Command: ')) {
                    return `<span class="log-command">${line}</span>`;
                }
                return line;
            }).join('\n');
            
            const container = document.getElementById('logContainer');
            if (container.innerHTML !== formattedLogs) {
                const isAtBottom = (container.scrollHeight - container.scrollTop) <= (container.clientHeight + 50);
                container.innerHTML = formattedLogs;
                if (isAtBottom) {
                    scrollToBottom();
                }
            }
        }
        
        // 3. Update LIVE badge and Progress
        try {
            const taskRes = await fetch('/api/tasks');
            const taskData = await taskRes.json();
            const task = taskData.tasks.find(t => t.id === taskId);
            updateLiveBadge(task && (task.status === 'downloading' || task.status === 'processing'));
            
            if (task) {
                const progressBar = document.getElementById('logProgressBar');
                const progressText = document.getElementById('logProgressText');
                if (progressBar && progressText) {
                    progressBar.style.width = `${task.progress}%`;
                    progressText.textContent = `${task.progress}%`;
                }
            }
        } catch (e) {
            console.error('Error updating live badge or progress:', e);
        }
    } catch (e) {
        console.error('Error fetching logs:', e);
    }
}

function updateMetricBar(type, value) {
    const valEl = document.getElementById(`${type}Val`);
    const barEl = document.getElementById(`${type}Bar`);
    if (!valEl || !barEl) return;
    
    valEl.textContent = Math.round(value);
    barEl.style.width = `${value}%`;
    
    let color = 'var(--success)';
    if (value > 70) color = 'orange';
    if (value > 90) color = 'var(--error)';
    barEl.style.background = color;
}

function scrollToBottom() {
    const container = document.getElementById('logContainer');
    container.scrollTop = container.scrollHeight;
}

async function copyLogsToClipboard() {
    const container = document.getElementById('logContainer');
    const text = container.innerText;
    
    if (!text) {
        showToast('No logs to copy', 'info');
        return;
    }

    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            showToast('Logs copied to clipboard!', 'success');
        } else {
            throw new Error('Clipboard API unavailable');
        }
    } catch (e) {
        try {
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-//9999px";
            textArea.style.top = "0";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            if (successful) {
                showToast('Logs copied to clipboard! (fallback)', 'success');
            } else {
                throw new Error('execCommand copy failed');
            }
        } catch (fallbackError) {
            console.error('Copy failed:', fallbackError);
            showToast('Failed to copy logs', 'error');
        }
    }
}

async function refreshLogs() {
    if (window.activeLogTaskId) {
        await fetchLogs(window.activeLogTaskId);
        showToast('Logs refreshed', 'info');
    }
}

function closeLogs() {
    document.getElementById('logModal').classList.remove('active');
    if (window.logPollingInterval) {
        clearInterval(window.logPollingInterval);
        window.logPollingInterval = null;
    }
    window.activeLogTaskId = null;
}

function toggleAllFiles(source, containerId) {
const container = document.getElementById(containerId);
const checkboxes = container.querySelectorAll('.file-checkbox');
checkboxes.forEach(cb => {
    cb.checked = source.checked;
    handleFileSelection(cb);
});
}

async function checkThumbnailStatus(filename) {
    try {
        const response = await fetch(`/api/thumbnails/${encodeURIComponent(filename)}`);
        if (response.status === 206) {
            const data = await response.json();
            return data.status === 'corrupted';
        }
    } catch (e) {
        console.error(`Status check failed for ${filename}:`, e);
    }
    return false;
}

window.loadLibraryRequestId = 0;

function toggleLibraryLoading(isLoading) {
    const listOriginals = document.getElementById('libraryListOriginals');
    const listCompressed = document.getElementById('libraryListCompressed');
    
    if (isLoading) {
        const skeletons = Array.from({ length: 5 }).map(() => `
            <div class="skeleton-row">
                <div class="skeleton skeleton-thumb"></div>
                <div class="skeleton-text">
                    <div class="skeleton skeleton-line"></div>
                    <div class="skeleton skeleton-line short"></div>
                </div>
                <div class="skeleton skeleton-btn"></div>
            </div>
        `).join('');
        
        listOriginals.innerHTML = skeletons;
        listCompressed.innerHTML = '';
    } else {
        // The actual data replacement happens in loadLibrary
    }
}

async function loadLibrary() {
    const listOriginals = document.getElementById('libraryListOriginals');
    const listCompressed = document.getElementById('libraryListCompressed');

    // Concurrency guard
    const requestId = ++window.loadLibraryRequestId;
    
    toggleLibraryLoading(true);

    try {
        const response = await apiFetch('/api/library');
        const data = await response.json();
        
        if (requestId !== window.loadLibraryRequestId) return;
        
        // Use a DocumentFragment to avoid multiple reflows and potential race conditions
        const fragOriginals = document.createDocumentFragment();
        const fragCompressed = document.createDocumentFragment();
        
        if(data.files.length === 0) {
            toggleLibraryLoading(false);
            listOriginals.innerHTML = `
                <div class="empty-state">
                    <div class="icon">📚</div>
                    <h3>Your library is empty</h3>
                    <p>All your downloaded and compressed VODs will appear here.</p>
                </div>
            `;
            listCompressed.innerHTML = '';
            return;
        }
    
        // Process thumbnail status checks concurrently
        const fileDataWithStatus = await Promise.all(data.files.map(async (file) => {
            const isIncomplete = await checkThumbnailStatus(file.filename);
            return { ...file, isIncomplete };
        }));

        for (const file of fileDataWithStatus) {
            const item = document.createElement('div');
            item.className = 'file-item';
            
            let sizeInfo = `Size: ${file.size}`;
            if (file.savings) {
                sizeInfo += ` | <span style="color: var(--success); font-weight: bold;">Saved: ${file.savings}</span>`;
            }
            
            const encoderBadge = file.encoder_type 
                ? `<span class="badge ${file.encoder_type === 'HW' ? 'badge-hw' : 'badge-sw'}">${file.encoder_type}</span>` 
                : '';
            
            const thumbUrl = `/api/thumbnails/${encodeURIComponent(file.filename)}`;
            const createdDate = file.created_at ? new Date(file.created_at).toLocaleString() : 'Unknown Date';
            
            const thumbHtml = file.isIncomplete 
                ? `<div class="thumb-preview incomplete" style="background: #333; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 0.6rem; color: var(--text-dim); border: 1px dashed #555;">⚠️<br>Incomplete</div>`
                : `<img src="${thumbUrl}" class="thumb-preview" alt="preview" onerror="this.classList.add('error')">`;
    
            item.innerHTML = `
                <div class="checkbox-wrapper">
                    <input type="checkbox" class="file-checkbox" data-filename="${encodeURIComponent(file.filename)}" onchange="handleFileSelection(this)">
                </div>
                ${thumbHtml}
                <div class="file-details">
                    <h4 class="file-name">${file.filename}</h4>
                    <div class="file-meta">
                        <span class="meta-item">${sizeInfo}</span>
                        <span class="meta-item">• Type: ${file.type}</span>
                        <span class="meta-item">• ${createdDate}</span>
                        ${encoderBadge}
                    </div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <a class="btn-download" href="/downloads/${file.filename}">Download to PC</a>
                    ${file.video_id ? `<button onclick="previewVideo('${file.video_id}')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: none; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>` : ''}
                </div>
            `;
            
            if (file.type === 'compress') {
                fragCompressed.appendChild(item);
            } else {
                fragOriginals.appendChild(item);
            }
        }
        
        if (requestId !== window.loadLibraryRequestId) return;

        toggleLibraryLoading(false);

        // Clear and update in one go at the end
        listOriginals.innerHTML = '';
        listOriginals.appendChild(fragOriginals);
        
        listCompressed.innerHTML = '';
        listCompressed.appendChild(fragCompressed);
    
    } catch (e) {
        toggleLibraryLoading(false);
        console.error('Library load failed:', e);
    }
}




async function loadFavorites() {
    try {
        const response = await fetch('/api/favorites');
        const data = await response.json();
        const grid = document.getElementById('favoritesGrid');
        grid.innerHTML = '';
        
        if(data.favorites.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <div class="icon">❤️</div>
                    <h3>No favorite channels</h3>
                    <p>Search for your favorite streamers and save them here for quick access.</p>
                </div>
            `;
            return;
        }
        
        data.favorites.forEach(fav => {
            const channel = fav.channel_name;
            const card = document.createElement('div');
            card.className = 'fav-card';
            
            const thumbUrl = fav.profile_image_url || `https://api.dicebear.com/7.x/initials/svg?seed=${channel}`;
            
            card.innerHTML = `
                <img src="${thumbUrl}" alt="avatar">
                <div class="fav-card-info">
                    <span class="fav-card-name">${channel}</span>
                    <p class="fav-card-description">${fav.description || 'No description available.'}</p>
                    <a href="https://twitch.tv/${channel}" target="_blank" class="fav-card-link">Visit Twitch Profile ↗</a>
                </div>
                <button class="fav-card-remove" onclick="removeFavorite('${channel}', event)" data-tooltip="Remove from Favorites">✕</button>
            `;
            card.onclick = () => {
                document.getElementById('channelInput').value = channel;
                window.showTab('search');
                searchVideos();
            };
            grid.appendChild(card);
        });
    } catch (e) {
        console.error('Failed to load favorites:', e);
    }
}

async function addFavToAutomation(channel, event) {
    event.stopPropagation();
    try {
        const response = await fetch('/api/monitored', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel_name: channel })
        });
        const data = await response.json();
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast(`Monitoring ${channel} started!`, 'success');
            loadMonitored();
        }
    } catch (e) {
        showToast('Error adding channel', 'error');
    }
}

async function loadMonitored() {
    try {
        const response = await fetch('/api/monitored');
        const data = await response.json();
        const list = document.getElementById('automationList');
        list.innerHTML = '';

        if (data.channels.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="icon">🤖</div>
                    <h3>No monitored channels</h3>
                    <p>Add a channel to automatically download their new VODs.</p>
                </div>
            `;
            return;
        }

        data.channels.forEach(c => {
            const item = document.createElement('div');
            item.className = `automation-card ${c.enabled ? 'enabled' : ''}`;
            item.innerHTML = `
                <div class="automation-header">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <h4>${c.channel_name}</h4>
                        <span class="badge ${c.enabled ? 'badge-hw' : 'badge-sw'}" style="font-size: 0.6rem;">${c.enabled ? 'Active' : 'Disabled'}</span>
                    </div>
                    <button onclick="deleteMonitored(${c.id})" style="background: var(--error); padding: 5px 10px; font-size: 0.7rem;" data-tooltip="Stop monitoring this channel">Remove</button>
                </div>
                <div class="automation-body">
                    <div class="automation-section">
                        <div class="automation-section-title">General</div>
                        <div class="settings-group toggles">
                            <div class="setting-item">
                                <input type="checkbox" ${c.enabled ? 'checked' : ''} onchange="updateMonitored(${c.id}, {enabled: this.checked}); this.closest('.automation-card').classList.toggle('enabled', this.checked)">
                                <span>Enabled</span>
                            </div>
                            <div class="setting-item">
                                <input type="checkbox" ${c.auto_compress ? 'checked' : ''} onchange="updateMonitored(${c.id}, {auto_compress: this.checked})">
                                <span>Auto-Compress</span>
                            </div>
                        </div>
                    </div>
                    <div class="automation-section">
                        <div class="automation-section-title">Compression Settings</div>
                        <div class="automation-settings">
                            <div class="settings-group">
                                <div class="setting-item">
                                    <label>Codec:</label>
                                    <select onchange="updateMonitored(${c.id}, {target_codec: this.value})">
                                        <option value="AV1" ${c.target_codec === 'AV1' ? 'selected' : ''}>AV1</option>
                                        <option value="H.264" ${c.target_codec === 'H.264' ? 'selected' : ''}>H.264</option>
                                        <option value="H.265" ${c.target_codec === 'H.265' ? 'selected' : ''}>H.265</option>
                                    </select>
                                </div>
                                <div class="setting-item">
                                    <label>Presets:</label>
                                    <select onchange="updateMonitored(${c.id}, {compression_presets: this.value})">
                                        <option value="fast" ${c.compression_presets === 'fast' ? 'selected' : ''}>Fast</option>
                                        <option value="balanced" ${c.compression_presets === 'balanced' ? 'selected' : ''}>Balanced</option>
                                        <option value="high" ${c.compression_presets === 'high' ? 'selected' : ''}>High Quality</option>
                                    </select>
                                </div>
                                <div class="setting-item">
                                    <input type="checkbox" ${c.delete_original ? 'checked' : ''} onchange="updateMonitored(${c.id}, {delete_original: this.checked})">
                                    <span>Delete Original</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            list.appendChild(item);
        });
                } catch (e) {
                    console.error('Failed to load monitored channels:', e);
            }
        }

        async function addMonitoredChannel() {

    const input = document.getElementById('autoChannelInput');
    const channel_name = input.value.trim();
    if (!channel_name) return;

    try {
        const response = await fetch('/api/monitored', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel_name })
        });
        const data = await response.json();
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast(`Monitoring ${channel_name} started!`, 'success');
            input.value = '';
            loadMonitored();
        }
    } catch (e) {
        showToast('Error adding channel', 'error');
    }
}

async function updateMonitored(id, settings) {
    try {
        await fetch('/api/monitored', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, ...settings })
        });
    } catch (e) {
        showToast('Failed to update settings', 'error');
    }
}

async function deleteMonitored(id) {
    if (!confirm('Stop monitoring this channel?')) return;
    try {
        await fetch('/api/monitored', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        loadLMonitored();
        loadMonitored();
    } catch (e) {
        showToast('Error removing channel', 'error');
    }
}


async function removeFavorite(channel, event) {
    event.stopPropagation();
    if (!confirm(`Remove ${channel} from favorites?`)) return;
    await toggleFavorite(channel);
}

function handleFileSelection(checkbox) {
    const item = checkbox.closest('.file-item');
    if (checkbox.checked) item.classList.add('selected');
    else item.classList.remove('selected');
    
    const selected = document.querySelectorAll('.file-checkbox:checked');
    const bulkBar = document.getElementById('bulkActions');
    const countSpan = document.getElementById('selectedCount');
    
    if (selected.length > 0) {
        bulkBar.classList.add('active');
        countSpan.textContent = `${selected.length} selected`;
    } else {
        bulkBar.classList.remove('active');
    }
}

async function bulkDelete() {
    const selected = Array.from(document.querySelectorAll('.file-checkbox:checked'))
                            .map(cb => decodeURIComponent(cb.dataset.filename));
    
    if (!confirm(`Delete ${selected.length} selected files?`)) return;
    
    try {
        const response = await fetch('/api/library/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filenames: selected })
        });
        const data = await response.json();
        if (data.message) {
            showToast(data.message, 'success');
            loadLibrary();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (e) {
        alert('An error occurred during bulk deletion.');
    }
}

async function bulkCompress() {
    document.getElementById('compressModal').classList.add('active');
}

function closeCompressModal() {
    document.getElementById('compressModal').classList.remove('active');
}

async function confirmBulkCompress() {
    const selected = Array.from(document.querySelectorAll('.file-checkbox:checked'))
                            .map(cb => decodeURIComponent(cb.dataset.filename));
    
    if (selected.length === 0) {
        showToast('No files selected', 'error');
        return;
    }

    const codec = document.getElementById('bulkCodec').value;
    const preset = document.getElementById('bulkPreset').value;
    
    closeCompressModal();

    try {
        const response = await fetch('/api/library/bulk-compress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filenames: selected, codec, preset })
        });
        const data = await response.json();
        if (data.message) {
            showToast(data.message, 'success');
            if(data.taskIds && data.taskIds.length > 0) {
                window.showTab('tasks');
            }
        } else {
            alert('Error: ' + data.error);
        }
    } catch (e) {
        alert('An error occurred during bulk compression.');
    }
}


async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();
        const list = document.getElementById('fileList');
        list.innerHTML = '';
        data.files.filter(file => !file.startsWith('compressed_')).forEach(fileData => {
            const file = typeof fileData === 'string' ? fileData : fileData.filename;
            const size = fileData.size || 'Unknown';
            const created = fileData.created_at ? new Date(fileData.created_at).toLocaleString() : 'Unknown Date';
            const videoId = fileData.video_id;

            const item = document.createElement('div');
            item.className = 'file-item';
            
            const thumbUrl = `/api/thumbnails/${encodeURIComponent(file)}`;
            
            item.innerHTML = `
                <div class="checkbox-wrapper">
                    <input type="checkbox" class="file-checkbox" data-filename="${encodeURIComponent(file)}" onchange="handleFileSelection(this)">
                </div>
                <img src="${thumbUrl}" class="thumb-preview" style="width: 120px; height: 68px;" alt="preview" onerror="this.classList.add('error')">
                <div class="file-details">
                    <h4 class="file-name">${file}</h4>
                    <div class="file-meta">
                            <span class="meta-item">Size: ${size}</span>
                            <span class="meta-item">• ${created}</span>
                    </div>
                </div>
                <div class="compress-controls">
                    ${videoId ? `<button onclick="previewVideo('${videoId}')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: none; transition: 0.2s; margin-right: 10px;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>` : ''}
                    <select id="codec-${encodeURIComponent(file)}">
                        <option value="AV1" selected>AV1</option>
                        <option value="H.264">H.264</option>
                        <option value="H.265">H.265</option>
                        <option value="x264">x264 (SW)</option>
                    </select>
                    <select id="preset-${encodeURIComponent(file)}">
                        <option value="fast">Fast</option>
                        <option value="balanced" selected>Balanced</option>
                        <option value="high">High Quality</option>
                    </select>
                    <button class="compress-btn" data-filename="${encodeURIComponent(file)}">Compress</button>
                </div>
            `;
            
            item.querySelector('.compress-btn').onclick = () => {
                const codec = document.getElementById(`codec-${encodeURIComponent(file)}`).value;
                compressFile(decodeURIComponent(file), codec);
            };
            
            list.appendChild(item);
        });
    } catch (e) {
        console.error('Load files failed:', e);
    }
}

async function compressFile(file, codec) {
    const preset = document.getElementById(`preset-${encodeURIComponent(file)}`).value;
    const response = await fetch('/api/compress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file, preset, codec })
    });
    const data = await response.json();
    if(data.taskId) {
        window.showTab('tasks');
    } else if(data.error) {
        showToast(data.error, 'info');
    }
}

async function clearFailedTasks() {
    if (!confirm('Clear all failed tasks?')) return;
    try {
        const response = await fetch('/api/tasks/clear_failed', { method: 'POST' });
        const data = await response.json();
        if (data.message) {
            showToast(data.message, 'success');
            loadTasks();
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (e) {
        showToast('An error occurred while clearing tasks.', 'error');
    }
}

async function cancelTask(taskId) {
    if (!confirm('Cancel this task?')) return;
    try {
        const response = await fetch(`/api/tasks/cancel/${taskId}`, { method: 'POST' });
        const data = await response.json();
        if (data.message) {
            loadTasks();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (e) {
        alert('An error occurred while cancelling the task.');
    }
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const btn = document.querySelector('.sidebar-toggle');
    sidebar.classList.toggle('collapsed');
    btn.textContent = sidebar.classList.contains('collapsed') ? '▶' : '◀';
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.onclick = () => toast.remove();
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

async function retryTask(taskId) {
    try {
        const response = await apiFetch(`/api/tasks/retry/${taskId}`, { method: 'POST' });
        const data = await response.json();
        if (data.message) {
            showToast(data.message, 'success');
            loadTasks();
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (e) {
        showToast('An error occurred while retrying the task.', 'error');
    }
}

async function loadTasks() {
    try {
        const response = await apiFetch('/api/tasks');
        const data = await response.json();
        const list = document.getElementById('taskList');
        
        // Toast notification logic: detect status changes
        if (window.lastTaskStatuses) {
            data.tasks.forEach(task => {
                const prevStatus = window.lastTaskStatuses[task.id];
                if (prevStatus && prevStatus !== task.status) {
                    if (task.status === 'completed') {
                        showToast(`Task completed: ${task.filename || 'VOD'}`, 'success');
                    } else if (task.status === 'error') {
                        showToast(`Task failed: ${task.filename || 'VOD'}`, 'error');
                    }
                }
            });
        }
        window.lastTaskStatuses = {};
        data.tasks.forEach(task => {
            window.lastTaskStatuses[task.id] = task.status;
        });
    
        if (data.tasks.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="icon">⏳</div>
                    <h3>No active tasks</h3>
                    <p>Your download and compression queue is currently empty.</p>
                </div>
            `;
            return;
        }
    
        list.innerHTML = '';
        data.tasks.forEach(task => {
            const item = document.createElement('div');
            item.className = 'task-item';
            
            let actionHtml = '';
                if(task.status === 'completed') {
                    const fileLink = task.filename ? `<a class="btn-download" href="/downloads/${task.filename}">Download File</a>` : `<span style="color: var(--text-dim); font-size: 0.8rem;">File not ready...</span>`;
                    const previewBtn = task.video_id ? `<button onclick="previewVideo('${task.video_id}')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: none; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>` : '';
                    actionHtml = `<div style="display: flex; align-items: center; gap: 8px;"><span style="color: var(--success); font-size: 1.2rem;">✅</span>${fileLink}${previewBtn}</div>`;
                } else if(task.status === 'error') {
                actionHtml = `
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="color: var(--error); font-size: 1.2rem;">❌</span>
                        <span style="color: var(--error); font-size: 0.8rem;">Failed</span>
                        ${task.type === 'compress' ? `<button onclick="retryTask(${task.id})" style="background: var(--primary); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.7rem; padding: 2px 6px;">Retry</button>` : ''}
                    </div>
                `;
            } else {
                actionHtml = `
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <span class="task-status">${task.status}...</span>
                        <button onclick="cancelTask(${task.id})" style="background: #444; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.7rem; padding: 2px 6px;">Cancel</button>
                    </div>
                `;
            }
    
                const encoderBadge = task.encoder_type 
                    ? `<span class="badge ${task.encoder_type === 'HW' ? 'badge-hw' : 'badge-sw'}">${task.encoder_type}</span>` 
                    : '';

                item.innerHTML = `
                    <div class="task-info">
                        <div style="flex: 1;">
                            <h4>${task.filename || 'VOD ' + (task.video_id || '')} ${encoderBadge} <span style="color: var(--text-dim); font-weight: normal; font-size: 0.8rem;">(${task.size})</span></h4>
                                 <div class="progress-container" style="position: relative; background: #333; height: 12px; border-radius: 6px; overflow: hidden; margin: 10px 0;">
                                     <div class="progress-bar ${task.status === 'downloading' || task.status === 'processing' ? 'active' : ''}" style="width: ${task.progress}%; height: 100%; background: var(--primary); transition: width 0.5s ease;"></div>
                                     <span class="progress-text" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: bold; color: white; text-shadow: 0 0 2px black; pointer-events: none;">${task.progress}%</span>
                                 </div>

                            <button onclick="viewTaskLogs(${task.id})" style="background: none; color: var(--primary); border: none; font-size: 0.7rem; cursor: pointer; padding: 0; margin-top: 4px; text-decoration: underline;" data-tooltip="View detailed processing logs">View Logs</button>
                        </div>
                    </div>
                    ${actionHtml}
                    ${task.status === 'error' ? `<span style="color: var(--error); cursor: help;" title="${task.error || 'Unknown error'}">⚠️</span>` : ''}
                `;
    
            list.appendChild(item);
        });
    } catch (e) {
        console.error('Task load failed:', e);
    }
}


// Expose critical functions to window for inline HTML handlers
window.searchVideos = searchVideos;
window.toggleFavorite = toggleFavorite;
window.downloadVideo = downloadVideo;
window.previewVideo = previewVideo;
window.closePreview = closePreview;
window.viewTaskLogs = viewTaskLogs;
window.closeLogs = closeLogs;
window.copyLogsToClipboard = copyLogsToClipboard;
window.refreshLogs = refreshLogs;
window.scrollToBottom = scrollToBottom;
window.addFavToAutomation = addFavToAutomation;
window.loadFavorites = loadFavorites;
window.loadLibrary = loadLibrary;
window.removeFavorite = removeFavorite;
window.handleFileSelection = handleFileSelection;
window.bulkDelete = bulkDelete;
window.bulkCompress = bulkCompress;
window.loadFiles = loadFiles;
window.compressFile = compressFile;
window.loadTasks = loadTasks;
window.clearFailedTasks = clearFailedTasks;
window.cancelTask = cancelTask;
window.retryTask = retryTask;
window.toggleSidebar = toggleSidebar;

function toggleAdminMenu() {
    const submenu = document.getElementById('adminSubmenu');
    if (!submenu) return;
    submenu.classList.toggle('active');
}

window.toggleAdminMenu = toggleAdminMenu;

// Initial tab load
const savedTab = localStorage.getItem('bigmoon_current_tab') || 'search';
showTab(savedTab);

// Polling for tasks
setInterval(() => {
    if (window.currentTab === 'tasks') {
        loadTasks();
    }
}, 3000);