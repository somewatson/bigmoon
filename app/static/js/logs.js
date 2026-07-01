async function viewTaskLogs(taskId) {
    const modal = document.getElementById('logModal');
    const container = document.getElementById('logContainer');
    const badgeEl = document.getElementById('logEncoderBadge');

    if (!modal || !container || !badgeEl) {
        console.error('Log modal elements not found in DOM');
        return;
    }

    modal.classList.add('active');
    container.innerHTML = 'Loading logs...';
    badgeEl.innerHTML = '';
    
    window.activeLogTaskId = taskId;
    
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
    if (!header) return;
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
        const metricsRes = await fetch('/api/system/metrics');
        const metricsData = await metricsRes.json();
        if (!metricsData.error) {
            updateMetricBar('cpu', metricsData.cpu);
            updateMetricBar('mem', metricsData.memory);
        }

        const response = await fetch(`/api/tasks/${taskId}/logs`);
        const data = await response.json();
        if (data.logs) {
            const lines = data.logs.split('\\n');
            const formattedLogs = lines.map(line => {
                if (line.startsWith('Command: ')) {
                    return `<span class="log-command">${line}</span> `;
                }
                return line;
            }).join('\\n');
            
            const container = document.getElementById('logContainer');
            if (container && container.innerHTML !== formattedLogs) {
                const isAtBottom = (container.scrollHeight - container.scrollTop) <= (container.clientHeight + 50);
                container.innerHTML = formattedLogs;
                if (isAtBottom) {
                    scrollToBottom();
                }
            }
        }
        
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
    if (container) container.scrollTop = container.scrollHeight;
}

async function copyLogsToClipboard() {
    const container = document.getElementById('logContainer');
    if (!container) return;
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
            textArea.style.left = "-9999px";
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
    const modal = document.getElementById('logModal');
    if (modal) modal.classList.remove('active');
    if (window.logPollingInterval) {
        clearInterval(window.logPollingInterval);
        window.logPollingInterval = null;
    }
    window.activeLogTaskId = null;
}

window.viewTaskLogs = viewTaskLogs;
window.closeLogs = closeLogs;
window.copyLogsToClipboard = copyLogsToClipboard;
window.refreshLogs = refreshLogs;
window.scrollToBottom = scrollToBottom;
