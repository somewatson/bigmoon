async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();
        const list = document.getElementById('fileList');
        list.innerHTML = '';
        
        const filteredFiles = data.files.filter(fileData => {
            const filename = typeof fileData === 'string' ? fileData : fileData.filename;
            return !filename.startsWith('compressed_');
        });

        // Sort by date (most recent first)
        filteredFiles.sort((a, b) => {
            const dateA = a.created_at ? new Date(a.created_at) : new Date(0);
            const dateB = b.created_at ? new Date(b.created_at) : new Date(0);
            return dateB - dateA;
        });

        filteredFiles.forEach(fileData => {
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

window.loadFiles = loadFiles;
window.compressFile = compressFile;
