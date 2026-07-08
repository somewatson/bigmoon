async function loadFavorites() {
    const grid = document.getElementById('favoritesGrid');
    grid.innerHTML = '<div class="empty-state"><div class="loader-spinner"></div><p>Loading favorites...</p></div>';
    try {
        const response = await fetch('/api/favorites');
        const data = await response.json();
        grid.innerHTML = '';
        
        if(data.favorites.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; text-align: center;">
                    <div class="icon" style="font-size: 3rem; cursor: pointer;" onclick="window.showTab('search')">❤️</div>
                    <h3 style="cursor: pointer;" onclick="window.showTab('search')">No favorite channels</h3>
                    <p>Click here to search for your favorite streamers and save them here for quick access.</p>
                </div>
            `;
        } else {
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
        }
        
        // Recommended Channels Section
        const recs = ['puddotv', 'shodesu', 'omegamixed', 'somewatson', 'sedurrr', 'dropscollectors'];
        const recsSection = document.createElement('div');
        recsSection.style.gridColumn = '1 / -1';
        recsSection.style.marginTop = '40px';
        recsSection.innerHTML = `
            <h3 style="margin-bottom: 10px; color: var(--text-dim);">Recommended (Washodo members):</h3>
            <div class="recs-text-list" style="display: flex; flex-wrap: wrap; gap: 8px;">
                ${recs.map(channel => `
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <div class="rec-tag" onclick="document.getElementById('channelInput').value='${channel}'; window.showTab('search'); searchVideos();">${channel}</div>
                        <button class="fav-card-add" onclick="toggleFavorite('${channel}', event)" data-tooltip="Add to Favorites" style="background: transparent; border: 1px solid var(--primary); color: var(--primary); cursor: pointer; font-size: 0.8rem; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: 0.2s;" onmouseover="this.style.background='var(--primary)'; this.style.color='white'" onmouseout="this.style.background='transparent'; this.style.color='var(--primary)';">❤️</button>
                    </div>
                `).join('')}
            </div>
        `;
        
        grid.appendChild(recsSection);

    } catch (e) {
        console.error('Failed to load favorites:', e);
        grid.innerHTML = '<div class="empty-state"><p style="color: var(--error);">Error loading favorites.</p></div>';
    }
}

async function removeFavorite(channel, event) {
    if (event) event.stopPropagation();
    if (!confirm(`Remove ${channel} from favorites?`)) return;
    await toggleFavorite(channel);
}


window.loadFavorites = loadFavorites;
window.removeFavorite = removeFavorite;
