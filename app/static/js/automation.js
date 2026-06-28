async function populateFavAutomationGrid() {
    const grid = document.getElementById('favAutomationGrid');
    try {
        const response = await apiFetch('/api/favorites');
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

async function addFavToAutomation(channel, event) {
    event.stopPropagation();
    try {
        const response = await apiFetch('/api/monitored', {
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
        const response = await apiFetch('/api/monitored');
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
        const response = await apiFetch('/api/monitored', {
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
        await apiFetch('/api/monitored', {
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
        await apiFetch('/api/monitored', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        loadMonitored();
    } catch (e) {
        showToast('Error removing channel', 'error');
    }
}

window.populateFavAutomationGrid = populateFavAutomationGrid;
window.addFavToAutomation = addFavToAutomation;
window.loadMonitored = loadMonitored;
window.addMonitoredChannel = addMonitoredChannel;
window.updateMonitored = updateMonitored;
window.deleteMonitored = deleteMonitored;
