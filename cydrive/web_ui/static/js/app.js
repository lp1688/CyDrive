let allFiles = [];

document.addEventListener("DOMContentLoaded", () => {
    loadDriveData();
    setupDropZone();
    setupSearch();
});

async function loadDriveData() {
    try {
        const [statsRes, filesRes] = await Promise.all([
            fetch("/api/stats"),
            fetch("/api/files")
        ]);

        if (statsRes.ok) {
            const stats = await statsRes.json();
            updateStatsUI(stats);
        }

        if (filesRes.ok) {
            allFiles = await filesRes.json();
            renderFilesTable(allFiles);
        }
    } catch (err) {
        console.error("Error loading drive data:", err);
    }
}

function updateStatsUI(stats) {
    document.getElementById("stat-total-files").innerText = stats.total_files;
    
    const mb = (stats.total_bytes / (1024 * 1024)).toFixed(1);
    const gb = (stats.total_bytes / (1024 * 1024 * 1024)).toFixed(2);
    const sizeStr = stats.total_bytes > (1024 * 1024 * 1024) ? `${gb} GB` : `${mb} MB`;
    
    document.getElementById("stat-total-size").innerText = sizeStr;
    document.getElementById("storage-detail").innerText = `${sizeStr} / Unlimited`;
}

function renderFilesTable(files) {
    const tbody = document.getElementById("files-tbody");
    document.getElementById("file-count-label").innerText = `${files.length} items`;

    if (!files || files.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                    <i class="fa-solid fa-folder-open" style="font-size: 2rem; margin-bottom: 0.5rem; display: block;"></i>
                    No files found in your CyDrive. Drag and drop files above to start!
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = files.map(file => {
        const icon = getFileIcon(file.name, file.is_dir);
        const sizeStr = file.is_dir ? "-" : formatBytes(file.size);
        const dateStr = file.mtime ? new Date(file.mtime * 1000).toLocaleDateString() : "-";
        const statusBadge = file.is_uploaded 
            ? '<span class="badge-status badge-synced"><i class="fa-solid fa-circle-check"></i> Synced</span>'
            : '<span class="badge-status badge-uploading"><i class="fa-solid fa-rotate fa-spin"></i> Syncing</span>';

        return `
            <tr>
                <td>
                    <div class="file-name-cell">
                        ${icon}
                        <span>${escapeHtml(file.name)}</span>
                    </div>
                </td>
                <td>${sizeStr}</td>
                <td>${statusBadge}</td>
                <td>${dateStr}</td>
                <td>
                    <a href="/api/download/${encodeURIComponent(file.name)}" class="action-btn" title="Download"><i class="fa-solid fa-download"></i></a>
                    ${isMedia(file.name) ? `<button class="action-btn" title="Preview" onclick="previewMedia('${encodeURIComponent(file.name)}')"><i class="fa-solid fa-play"></i></button>` : ''}
                </td>
            </tr>
        `;
    }).join("");
}

function getFileIcon(name, isDir) {
    if (isDir) return '<i class="fa-solid fa-folder" style="color: #ffd166; font-size: 1.2rem;"></i>';
    const ext = name.split('.').pop().toLowerCase();
    
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) {
        return '<i class="fa-solid fa-file-image" style="color: #00f3ff; font-size: 1.2rem;"></i>';
    } else if (['mp4', 'mkv', 'avi', 'mov'].includes(ext)) {
        return '<i class="fa-solid fa-file-video" style="color: #ff007f; font-size: 1.2rem;"></i>';
    } else if (['mp3', 'wav', 'flac', 'ogg'].includes(ext)) {
        return '<i class="fa-solid fa-file-audio" style="color: #c084fc; font-size: 1.2rem;"></i>';
    } else if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) {
        return '<i class="fa-solid fa-file-zipper" style="color: #f77f00; font-size: 1.2rem;"></i>';
    } else if (['pdf', 'doc', 'docx', 'txt'].includes(ext)) {
        return '<i class="fa-solid fa-file-lines" style="color: #00ff88; font-size: 1.2rem;"></i>';
    }
    return '<i class="fa-solid fa-file" style="color: #8b9bb4; font-size: 1.2rem;"></i>';
}

function isMedia(name) {
    const ext = name.split('.').pop().toLowerCase();
    return ['mp4', 'webm', 'mp3', 'wav', 'jpg', 'png', 'gif', 'webp'].includes(ext);
}

function previewMedia(fileName) {
    const decoded = decodeURIComponent(fileName);
    const ext = decoded.split('.').pop().toLowerCase();
    const modal = document.getElementById("media-modal");
    const modalTitle = document.getElementById("modal-title");
    const modalBody = document.getElementById("modal-body");

    modalTitle.innerText = decoded;
    const url = `/api/download/${fileName}`;

    if (['mp4', 'webm'].includes(ext)) {
        modalBody.innerHTML = `<video controls autoplay style="width: 100%; border-radius: 10px;"><source src="${url}"></video>`;
    } else if (['mp3', 'wav'].includes(ext)) {
        modalBody.innerHTML = `<audio controls autoplay style="width: 100%; margin-top: 1rem;"><source src="${url}"></audio>`;
    } else {
        modalBody.innerHTML = `<img src="${url}" style="max-width: 100%; max-height: 500px; border-radius: 10px; display: block; margin: 0 auto;">`;
    }

    modal.style.display = "flex";
}

function closeModal() {
    const modal = document.getElementById("media-modal");
    document.getElementById("modal-body").innerHTML = "";
    modal.style.display = "none";
}

function setupSearch() {
    const searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (!query) {
            renderFilesTable(allFiles);
            return;
        }
        const filtered = allFiles.filter(f => f.name.toLowerCase().includes(query));
        renderFilesTable(filtered);
    });
}

function setupDropZone() {
    const dropZone = document.getElementById("drop-zone");
    
    ['dragenter', 'dragover'].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFiles(files);
        }
    });

    dropZone.addEventListener('click', () => {
        document.getElementById('file-upload').click();
    });
}

function handleFileUpload(input) {
    if (input.files.length > 0) {
        uploadFiles(input.files);
    }
}

async function uploadFiles(files) {
    for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });
            if (res.ok) {
                console.log(`Uploaded ${file.name}`);
            }
        } catch (err) {
            console.error("Upload error:", err);
        }
    }
    loadDriveData();
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
