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
