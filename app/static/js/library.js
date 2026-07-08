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
    const sortBy = document.getElementById('librarySort').value;

    const requestId = ++window.loadLibraryRequestId;
    toggleLibraryLoading(true);

    try {
        const response = await apiFetch('/api/library');
        const data = await response.json();
        
        if (requestId !== window.loadLibraryRequestId) return;
        
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

        // Implement Sorting
        data.files.sort((a, b) => {
            if (sortBy === 'date') {
                return new Date(b.created_at || 0) - new Date(a.created_at || 0);
            } else if (sortBy === 'name') {
                return a.filename.localeCompare(b.filename);
            } else if (sortBy === 'size') {
                return (b.size_bytes || 0) - (a.size_bytes || 0);
            }
            return 0;
            return 0;
        });

        const fragOriginals = document.createDocumentFragment();
        const fragCompressed = document.createDocumentFragment();
        
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

            const escapedFilename = file.filename.replace(/'/g, "\\'");
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
                        ${file.user_id ? `<span class="meta-item" style="color: var(--text-dim); font-style: italic;">(User ID: ${file.user_id})</span>` : ''}
                        ${encoderBadge}
                    </div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <a class="btn-download" href="/downloads/${file.filename}">Download to PC</a>
                    ${(file.filename && !file.isIncomplete) ? `<button onclick="previewVideo('${escapedFilename}', 'file')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: none; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>` : ''}
                    ${file.video_id ? `<button onclick="viewChat('${file.video_id}')" style="background: #2a2a2a; color: #aaa; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: 1px solid #444; transition: 0.2s;" onmouseover="this.style.background='#333'; this.style.color='#fff'" onmouseout="this.style.background='#2a2a2a'; this.style.color='#aaa'" data-tooltip="View Chat">View Chat</button>` : ''}
                    ${file.video_id ? `<button onclick="window.open('/api/chat/export/${file.video_id}', '_blank')" style="background: #2a2a2a; color: #aaa; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: 1px solid #444; transition: 0.2s;" onmouseover="this.style.background='#333'; this.style.color='#fff'" onmouseout="this.style.background='#2a2a2a'; this.style.color='#aaa'" data-tooltip="Download Chat JSON">Chat JSON</button>` : ''}
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
        listOriginals.innerHTML = '';
        listOriginals.appendChild(fragOriginals);
        listCompressed.innerHTML = '';
        listCompressed.appendChild(fragCompressed);
    
    } catch (e) {
        toggleLibraryLoading(false);
        console.error('Library load failed:', e);
    }
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

window.checkThumbnailStatus = checkThumbnailStatus;
window.toggleLibraryLoading = toggleLibraryLoading;
window.loadLibrary = loadLibrary;
window.handleFileSelection = handleFileSelection;
window.bulkDelete = bulkDelete;
window.bulkCompress = bulkCompress;
window.closeCompressModal = closeCompressModal;
window.confirmBulkCompress = confirmBulkCompress;

function toggleAllFiles(checkbox, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const checkboxes = container.querySelectorAll('.file-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checkbox.checked;
        handleFileSelection(cb);
    });
}

window.toggleAllFiles = toggleAllFiles;

async function loadGlobalLibrary() {
    const grid = document.getElementById('globalLibraryGrid');
    if (!grid) return;

    grid.innerHTML = '<div class="empty-state">Loading community library...</div>';

    try {
        const response = await apiFetch('/api/library/global');
        const data = await response.json();

        if (!data.files || data.files.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="icon">🌍</div>
                    <h3>Global Library is empty</h3>
                    <p>No VODs have been archived by the community yet.</p>
                </div>
            `;
            return;
        }

        const frag = document.createDocumentFragment();
        
        for (const file of data.files) {
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
            
            const thumbHtml = `<img src="${thumbUrl}" class="thumb-preview" alt="preview" onerror="this.classList.add('error')">`;
            const escapedFilename = file.filename.replace(/'/g, "\\'");

            item.innerHTML = `
                <div class="checkbox-wrapper"></div>
                ${thumbHtml}
                <div class="file-details">
                    <h4 class="file-name">${file.filename}</h4>
                    <div class="file-meta">
                        <span class="meta-item">${sizeInfo}</span>
                        <span class="meta-item">• Type: ${file.type}</span>
                        <span class="meta-item">• ${createdDate}</span>
                        ${file.user_id ? `<span class="meta-item" style="color: var(--text-dim); font-style: italic;">(User ID: ${file.user_id})</span>` : ''}
                        ${encoderBadge}
                    </div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <a class="btn-download" href="/downloads/${file.filename}">Download to PC</a>
                    ${(file.filename) ? `<button onclick="previewVideo('${escapedFilename}', 'file')" style="background: #444; color: white; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: none; transition: 0.2s;" onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'" data-tooltip="Watch Preview">Preview</button>` : ''}
                    ${file.video_id ? `<button onclick="viewChat('${file.video_id}')" style="background: #2a2a2a; color: #aaa; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: 1px solid #444; transition: 0.2s;" onmouseover="this.style.background='#333'; this.style.color='#fff'" onmouseout="this.style.background='#2a2a2a'; this.style.color='#aaa'" data-tooltip="View Chat">View Chat</button>` : ''}
                    ${file.video_id ? `<button onclick="window.open('/api/chat/export/${file.video_id}', '_blank')" style="background: #2a2a2a; color: #aaa; font-size: 0.8rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: 1px solid #444; transition: 0.2s;" onmouseover="this.style.background='#333'; this.style.color='#fff'" onmouseout="this.style.background='#2a2a2a'; this.style.color='#aaa'" data-tooltip="Download Chat JSON">Chat JSON</button>` : ''}
                </div>
            `;
            frag.appendChild(item);
        }

        grid.innerHTML = '';
        grid.appendChild(frag);

    } catch (e) {
        grid.innerHTML = '<div class="empty-state">Failed to load global library.</div>';
        console.error('Global library load failed:', e);
    }
}

window.loadGlobalLibrary = loadGlobalLibrary;
