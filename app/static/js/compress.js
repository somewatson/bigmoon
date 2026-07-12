async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();
        const list = document.getElementById('fileList');
        list.innerHTML = '';
        
        // Fetch hardware capabilities to adapt UI
        let capabilities = { intel: false, qsv: false, vaapi: false, nvenc: false, amf: false, capabilities: [] };
        try {
            const capRes = await fetch('/api/system/capabilities');
            if (capRes.ok) capabilities = await capRes.json();
        } catch (e) {
            console.error('Failed to fetch capabilities:', e);
        }

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
            
            // Dynamic hardware options based on capabilities
            let hwOptions = `<option value="auto" selected>Auto (Recommended)</option>`;
            if (capabilities.intel) {
                if (capabilities.qsv) hwOptions += `<option value="qsv">Intel QuickSync (Fastest, HW) (Best)</option>`;
                if (capabilities.vaapi) hwOptions += `<option value="vaapi">VA-API (Fast, HW)</option>`;
            } else if (capabilities.capabilities.length > 0) {
                hwOptions += `<option value="hardware">Hardware Accelerated (Fast) (Best)</option>`;
            }
            hwOptions += `<option value="sw">Software (Slowest, High Quality)</option>`;

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
                <div style="display: flex; align-items: center; gap: 5px;">
                    <select id="codec-${encodeURIComponent(file)}">
                        <option value="AV1" selected>AV1</option>
                        <option value="H.264">H.264</option>
                        <option value="H.265">H.265</option>
                        <option value="x264">x264 (SW)</option>
                    </select>
                    <span style="cursor: help; font-size: 0.8rem; color: var(--text-dim);" data-tooltip="AV1: Best compression, high CPU. H.264: Max compatibility. H.265: Balanced. x264: High quality software encoding.">ⓘ</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <select id="hwpref-${encodeURIComponent(file)}">
                        ${hwOptions}
                    </select>
                    <span style="cursor: help; font-size: 0.8rem; color: var(--text-dim);" data-tooltip="Hardware acceleration uses your GPU to encode videos much faster than your CPU.">ⓘ</span>
                </div>
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
    const hw_pref = document.getElementById(`hwpref-${encodeURIComponent(file)}`).value;
    const response = await fetch('/api/compress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file, preset, codec, hw_pref })
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
