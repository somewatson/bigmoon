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
    
    const url = new URL(window.location);
    url.searchParams.set('tab', tabId);
    window.history.pushState({ tab: tabId }, '', url);

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
    
    if (window.showTabGlobal) {
        window.showTabGlobal(tabId);
    }
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

window.apiFetch = apiFetch;
window.updateConnectionStatus = updateConnectionStatus;
window.showTab = showTab;
window.showToast = showToast;
