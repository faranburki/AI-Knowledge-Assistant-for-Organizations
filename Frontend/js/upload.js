/**
 * upload.js — Handles file selection, fake upload progress, and documents table
 * DocuMind AI Frontend
 *
 * Backend integration note:
 *   Replace `simulateUpload()` with a fetch() POST to /api/upload
 *   using FormData to send the actual file.
 */

/* ── Page loader ──────────────────────────────────────── */
window.addEventListener('load', () => {
  const loader = document.getElementById('pageLoader');
  if (loader) setTimeout(() => loader.classList.add('hidden'), 300);
  renderDocumentsTable();
});

/* ── DOM references ───────────────────────────────────── */
const uploadZone   = document.getElementById('uploadZone');
const fileInput    = document.getElementById('fileInput');
const filePreview  = document.getElementById('filePreview');
const fileList     = document.getElementById('fileList');
const uploadBtn    = document.getElementById('uploadBtn');
const progressWrap = document.getElementById('progressWrap');
const progressBar  = document.getElementById('progressBar');
const progressPct  = document.getElementById('progressPct');
const docsTableBody= document.getElementById('docsTableBody');
const docCount     = document.getElementById('docCount');

/* ── Dummy existing documents ─────────────────────────── */
let documents = [
  { name: 'Student Handbook 2026.pdf',       type: 'PDF',  date: '2026-01-15', size: '3.2 MB', status: 'indexed'    },
  { name: 'Fee Policy 2026.pdf',             type: 'PDF',  date: '2026-01-20', size: '1.1 MB', status: 'indexed'    },
  { name: 'Hostel Rules & Regulations.docx', type: 'DOCX', date: '2026-02-05', size: '856 KB', status: 'indexed'    },
  { name: 'Academic Calendar 2026.pdf',      type: 'PDF',  date: '2026-02-18', size: '2.4 MB', status: 'indexed'    },
  { name: 'IT Infrastructure Policy.docx',   type: 'DOCX', date: '2026-03-01', size: '445 KB', status: 'processing' },
];

/* ── Utility: format file size ────────────────────────── */
function formatSize(bytes) {
  if (bytes < 1024)        return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/* ── Utility: get file extension ──────────────────────── */
function getExt(filename) {
  return filename.split('.').pop().toUpperCase();
}

/* ── Utility: today's date as YYYY-MM-DD ─────────────── */
function todayStr() {
  return new Date().toISOString().split('T')[0];
}

/* ── Render documents table ───────────────────────────── */
function renderDocumentsTable() {
  docsTableBody.innerHTML = '';

  if (documents.length === 0) {
    docsTableBody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <h5>No documents yet</h5>
            <p>Upload your first document above</p>
          </div>
        </td>
      </tr>`;
    docCount.textContent = '0 documents';
    return;
  }

  docCount.textContent = `${documents.length} document${documents.length !== 1 ? 's' : ''}`;

  documents.forEach((doc, idx) => {
    const statusMap = {
      indexed:    { label: 'Indexed',    cls: 'status-indexed'    },
      processing: { label: 'Processing', cls: 'status-processing' },
      failed:     { label: 'Failed',     cls: 'status-failed'     },
    };
    const s = statusMap[doc.status] || statusMap.indexed;
    const typeCls = doc.type === 'PDF' ? 'badge-pdf' : 'badge-docx';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:${doc.type==='PDF'?'#fef2f2':'#eff6ff'}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${doc.type==='PDF'?'#ef4444':'#3b82f6'}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div>
            <div style="font-weight:500;font-size:.875rem;color:var(--text-heading);">${doc.name}</div>
          </div>
        </div>
      </td>
      <td><span class="file-badge ${typeCls}">${doc.type}</span></td>
      <td style="color:var(--text-muted);">${doc.date}</td>
      <td style="color:var(--text-muted);">${doc.size}</td>
      <td>
        <span class="status-badge ${s.cls}">
          <span style="width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;"></span>
          ${s.label}
        </span>
      </td>
      <td>
        <button class="btn-secondary-custom delete-btn" data-idx="${idx}"
          style="padding:5px 10px;font-size:.75rem;color:#ef4444;border-color:transparent;">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
        </button>
      </td>
    `;
    docsTableBody.appendChild(tr);
  });

  // Delete handlers
  document.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx);
      const name = documents[idx].name;
      documents.splice(idx, 1);
      renderDocumentsTable();
      showToast('success', 'Document removed', `"${name}" has been deleted.`);
    });
  });
}

/* ── Handle file selection ────────────────────────────── */
function handleFiles(files) {
  const valid = [];
  const allowed = ['pdf', 'docx'];

  Array.from(files).forEach(file => {
    const ext = file.name.split('.').pop().toLowerCase();
    if (allowed.includes(ext)) {
      valid.push(file);
    } else {
      showToast('error', 'Invalid file type', `"${file.name}" is not a PDF or DOCX.`);
    }
  });

  if (valid.length === 0) return;

  // Show file preview
  filePreview.style.display = 'block';
  fileList.innerHTML = '';

  valid.forEach(file => {
    const ext = getExt(file.name);
    const typeCls = ext === 'PDF' ? 'badge-pdf' : 'badge-docx';
    const item = document.createElement('div');
    item.style.cssText = `
      display:flex;align-items:center;gap:10px;
      padding:10px 12px;
      background:var(--surface-2);
      border:1px solid var(--border);
      border-radius:var(--radius-sm);
    `;
    item.innerHTML = `
      <span class="file-badge ${typeCls}" style="flex-shrink:0;">${ext}</span>
      <span style="flex:1;font-size:.85rem;color:var(--text-heading);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${file.name}</span>
      <span style="font-size:.78rem;color:var(--text-muted);flex-shrink:0;">${formatSize(file.size)}</span>
    `;
    fileList.appendChild(item);
  });

  // Store files reference for upload
  uploadBtn._files = valid;
  uploadBtn.disabled = false;
}

/* ── File input change ────────────────────────────────── */
fileInput.addEventListener('change', (e) => {
  handleFiles(e.target.files);
});

/* ── Drag and drop ────────────────────────────────────── */
uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});

/* ── Simulate upload progress ─────────────────────────── */
function simulateUpload(files) {
  return new Promise((resolve) => {
    progressWrap.style.display = 'block';
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading…';

    let pct = 0;
    const interval = setInterval(() => {
      pct += Math.random() * 18 + 5;
      if (pct >= 100) {
        pct = 100;
        clearInterval(interval);
        setTimeout(resolve, 300);
      }
      progressBar.style.width = pct + '%';
      progressPct.textContent = Math.round(pct) + '%';
    }, 150);
  });
}

/* ── Upload button click ──────────────────────────────── */
uploadBtn.addEventListener('click', async () => {
  const files = uploadBtn._files;
  if (!files || files.length === 0) return;

  await simulateUpload(files);

  // Add uploaded files to documents list as "processing"
  files.forEach(file => {
    documents.unshift({
      name:   file.name,
      type:   getExt(file.name),
      date:   todayStr(),
      size:   formatSize(file.size),
      status: 'processing',
    });
  });

  // Simulate index completion after 2.5 seconds
  setTimeout(() => {
    documents.forEach(doc => {
      if (doc.status === 'processing') doc.status = 'indexed';
    });
    renderDocumentsTable();
    showToast('success', 'Indexing complete', 'Your documents are ready to query.');
  }, 2500);

  renderDocumentsTable();

  // Reset upload UI
  progressWrap.style.display = 'none';
  progressBar.style.width = '0%';
  progressPct.textContent = '0%';
  filePreview.style.display = 'none';
  fileList.innerHTML = '';
  fileInput.value = '';
  uploadBtn.disabled = true;
  uploadBtn.innerHTML = `
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
    Upload & Index Documents
  `;

  showToast('success', 'Upload complete', `${files.length} file${files.length > 1 ? 's' : ''} uploaded and being indexed.`);
});

/* ── Toast notification ───────────────────────────────── */
function showToast(type, title, message) {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  const iconHtml = type === 'success'
    ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;

  toast.className = `toast-custom toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${iconHtml}</div>
    <div class="toast-text">
      <h6>${title}</h6>
      <p>${message}</p>
    </div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 350);
  }, 3500);
}
