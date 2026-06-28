async function loadTasks() {
    try {
        const response = await apiFetch('/api/tasks');
        const data = await response.json();
        const list = document.getElementById('taskList');
        
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
                    const escapedFilename = task.filename ? task.filename.replace(/'/g, "\\'") : '';
                    const fileLink = task.filename ? `<a class="btn-download" href="/downloads/${task.filename}">Download File</a>` : `<span style="color: var(--text-dim); font-size: 0.8rem;">File not ready...</span>`;
                    const previewBtn = task.filename ? `<button onclick="previewVideo('${escapedFilename}')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: none; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>` : '';
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

async function viewTaskLogs(taskId) {
    const modal = document.getElementById('logModal');
    const container = document.getElementById('logContainer');
    const badgeEl = document.getElementById('logEncoderBadge');
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
            const lines = data.logs.split('\n');
            const formattedLogs = lines.map(line => {
                if (line.startsWith('Command: ')) {
                    return `<span class="log-command">${line}</span> `;
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

window.loadTasks = loadTasks;
window.viewTaskLogs = viewTaskLogs;
window.closeLogs = closeLogs;
window.copyLogsToClipboard = copyLogsToClipboard;
window.refreshLogs = refreshLogs;
window.scrollToBottom = scrollToBottom;
window.clearFailedTasks = clearFailedTasks;
window.cancelTask = cancelTask;
window.retryTask = retryTask;
