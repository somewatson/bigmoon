async function loadFavorites() {
    const grid = document.getElementById('favoritesGrid');
    grid.innerHTML = '<div class="empty-state"><div class="loader-spinner"></div><p>Loading favorites...</p></div>';
    try {
        const response = await fetch('/api/favorites');
        const data = await response.json();
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
        grid.innerHTML = '<div class="empty-state"><p style="color: var(--error);">Error loading favorites.</p></div>';
    }
}

async function removeFavorite(channel, event) {
    event.stopPropagation();
    if (!confirm(`Remove ${channel} from favorites?`)) return;
    await toggleFavorite(channel);
}

window.loadFavorites = loadFavorites;
window.removeFavorite = removeFavorite;
