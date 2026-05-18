/* ═══ Documents Page Logic ═══ */

async function loadDocuments() {
  const table = document.getElementById('docTable');
  const empty = document.getElementById('docEmpty');
  table.innerHTML = '<div style="padding:60px;display:flex;justify-content:center"><div class="spinner"></div></div>';
  empty.classList.add('hidden');

  try {
    const docs = await API.listDocuments();
    const user = API.getUser();
    const isAdmin = user && user.is_admin;

    // Toggle main upload button
    const headerBtn = document.getElementById('headerUploadBtn');
    if (headerBtn) {
      headerBtn.style.display = isAdmin ? 'inline-flex' : 'none';
    }

    if (!docs || docs.length === 0) {
      table.innerHTML = '';
      if (isAdmin) {
        empty.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <h3>No documents yet</h3>
          <p>Upload your first document to start building your knowledge base.</p>
          <button class="btn btn-primary" style="margin-top:16px" onclick="openUploadModal()">Upload document</button>
        `;
      } else {
        empty.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <h3>No documents yet</h3>
          <p>Please contact your administrator to upload knowledge base files.</p>
        `;
      }
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    table.innerHTML = `<div class="table-wrap" style="box-shadow:0 2px 8px rgba(0,0,0,0.02)">
      <table class="table">
        <thead><tr>
          <th>Document Title & Name</th>
          <th>Format</th>
          <th>Size</th>
          <th>Status</th>
          <th>Uploaded</th>
          ${isAdmin ? '<th style="text-align:right">Actions</th>' : ''}
        </tr></thead>
        <tbody>${docs.map(d => `<tr>
          <td>
            <div style="display:flex;align-items:center;gap:12px">
              <div style="width:36px;height:36px;border-radius:10px;background:var(--bg-secondary);border:1px solid var(--border-primary);display:flex;align-items:center;justify-content:center;color:var(--text-tertiary)">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              </div>
              <div style="max-width:300px">
                <div style="font-weight:600;font-size:14px;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(d.title || d.file_name)}</div>
                <div style="font-size:12px;color:var(--text-tertiary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(d.file_name)}</div>
              </div>
            </div>
          </td>
          <td><span class="badge badge-default" style="font-family:var(--font-mono)">${(d.file_type||'UNKNOWN').toUpperCase()}</span></td>
          <td style="color:var(--text-secondary);font-size:13px">${(d.file_size_mb||0).toFixed(2)} MB</td>
          <td>
            <div style="display:inline-flex;align-items:center;gap:6px;background:${d.status==='ready'?'var(--success-muted)':d.status==='error'?'var(--error-muted)':'var(--accent-muted)'};padding:4px 10px;border-radius:99px;border:1px solid ${d.status==='ready'?'#a7f3d0':d.status==='error'?'#fecaca':'#bfdbfe'}">
              <div style="width:6px;height:6px;border-radius:50%;background:${d.status==='ready'?'var(--success)':d.status==='error'?'var(--error)':'var(--accent)'}"></div>
              <span style="font-size:12px;font-weight:600;color:${d.status==='ready'?'#065f46':d.status==='error'?'#991b1b':'#1e40af'}">${(d.status||'ready').charAt(0).toUpperCase() + (d.status||'ready').slice(1)}</span>
            </div>
          </td>
          <td style="color:var(--text-tertiary);font-size:13px">${timeAgo(d.upload_date)}</td>
          ${isAdmin ? `
          <td style="text-align:right">
            <button class="icon-btn" onclick="deleteDoc('${d.document_id}')" data-tooltip="Delete Document" style="color:var(--text-tertiary)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </td>` : ''}
        </tr>`).join('')}</tbody>
      </table>
    </div>`;
  } catch (err) {
    table.innerHTML = `<div class="empty-state" style="border-color:#fecaca;background:var(--error-muted)"><h3 style="color:#991b1b">Failed to load knowledge base</h3><p style="color:#b91c1c">${err.message}</p></div>`;
  }
}

async function deleteDoc(docId) {
  if (!confirm('Are you sure you want to delete this document? This will remove all its vectors from the Knowledge Base.')) return;
  try {
    await API.deleteDocument(docId);
    showToast('Document successfully deleted', 'success');
    loadDocuments();
  } catch (err) { showToast('Deletion failed: ' + err.message, 'error'); }
}

// ── Upload Modal ────────────────────────────────────────────
function openUploadModal() {
  document.getElementById('uploadModal').classList.remove('hidden');
  selectedFile = null;
  document.getElementById('uploadProgress').classList.add('hidden');
  document.getElementById('uploadProgress').innerHTML = '';
  document.getElementById('uploadBtn').disabled = true;
  document.getElementById('uploadTitle').value = '';
  document.getElementById('uploadTags').value = '';
  document.getElementById('fileInput').value = '';
  
  // Restore form and footer visibility
  document.getElementById('uploadModalForm').classList.remove('hidden');
  const footer = document.querySelector('#uploadModal .modal-footer');
  if (footer) footer.classList.remove('hidden');
}
function closeUploadModal(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('uploadModal').classList.add('hidden');
}

function handleDragOver(e) { e.preventDefault(); e.currentTarget.classList.add('dragover'); }
function handleDragLeave(e) { e.currentTarget.classList.remove('dragover'); }
function handleDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('dragover');
  if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
}
function handleFileSelect(input) { if (input.files.length) selectFile(input.files[0]); }

function selectFile(file) {
  selectedFile = file;
  document.getElementById('uploadBtn').disabled = false;
  const prog = document.getElementById('uploadProgress');
  prog.classList.remove('hidden');
  prog.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;padding:16px;background:var(--bg-secondary);border:1px solid var(--border-primary);border-radius:12px">
    <div style="display:flex;align-items:center;gap:16px">
      <div style="width:40px;height:40px;background:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow-xs);border:1px solid var(--border-primary)">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      </div>
      <div>
        <div style="font-weight:600;font-size:14px;color:var(--text-primary);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(file.name)}</div>
        <div style="font-size:12px;color:var(--text-tertiary);margin-top:2px">${(file.size/1024/1024).toFixed(2)} MB</div>
      </div>
    </div>
    <button class="icon-btn" onclick="clearFile()" style="background:#fff;border:1px solid var(--border-primary);box-shadow:var(--shadow-xs)">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    </button>
  </div>`;
}

function clearFile() {
  selectedFile = null;
  document.getElementById('uploadBtn').disabled = true;
  document.getElementById('uploadProgress').classList.add('hidden');
  document.getElementById('fileInput').value = '';
}

async function performUpload() {
  if (!selectedFile) return;
  const btn = document.getElementById('uploadBtn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;border-top-color:#fff"></div> <span>Processing...</span>';

  // Show pipeline stages
  const prog = document.getElementById('uploadProgress');
  const stages = ['Upload', 'Extract Text', 'Chunking', 'Vector Embedding', 'Indexing'];
  
  // Clear any existing progress and show container
  prog.classList.remove('hidden');
  prog.innerHTML = '';

  // Create beautiful progress visualizer with a dynamic filling progress line
  prog.innerHTML += `<div style="margin-top:24px;border:1px solid var(--border-primary);border-radius:12px;padding:20px;background:#fff;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05)">
    <div style="font-size:12px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:16px">Pipeline Status</div>
    <div style="display:flex;justify-content:space-between;position:relative" id="pipelineStages">
      <div style="position:absolute;top:12px;left:20px;right:20px;height:2px;background:var(--bg-tertiary);z-index:0"></div>
      <div id="progressLine" style="position:absolute;top:12px;left:20px;width:0%;height:2px;background:var(--success);z-index:0;transition:width 0.8s cubic-bezier(0.4, 0, 0.2, 1)"></div>
      ${stages.map((s, i) => `
      <div style="display:flex;flex-direction:column;align-items:center;gap:8px;position:relative;z-index:1;width:60px" class="pipeline-stage" id="stage-${i}">
        <div class="stage-icon" style="width:24px;height:24px;border-radius:50%;background:var(--bg-tertiary);border:4px solid #fff;display:flex;align-items:center;justify-content:center;transition:all 0.4s cubic-bezier(0.4, 0, 0.2, 1);box-shadow:0 0 0 1px var(--border-primary)">
        </div>
        <span style="font-size:10px;font-weight:600;color:var(--text-tertiary);text-align:center;transition:all 0.4s cubic-bezier(0.4, 0, 0.2, 1)">${s}</span>
      </div>`).join('')}
    </div>
  </div>`;

  // UI state updater for individual stages
  const updateStageUI = (stageIdx, state) => {
    const el = document.getElementById('stage-' + stageIdx);
    if (!el) return;
    const icon = el.querySelector('.stage-icon');
    const label = el.querySelector('span');
    if (state === 'pending') {
      icon.style.background = 'var(--bg-tertiary)';
      icon.style.boxShadow = '0 0 0 1px var(--border-primary)';
      icon.style.transform = 'scale(1.0)';
      icon.innerHTML = '';
      label.style.color = 'var(--text-tertiary)';
      label.style.fontWeight = '600';
    } else if (state === 'active') {
      icon.style.background = 'var(--accent)';
      icon.style.boxShadow = '0 0 0 1px var(--accent)';
      icon.style.transform = 'scale(1.15)';
      icon.innerHTML = '<div style="width:6px;height:6px;border-radius:50%;background:#fff;animation:pulse 1.5s infinite"></div>';
      label.style.color = 'var(--text-primary)';
      label.style.fontWeight = '700';
    } else if (state === 'complete') {
      icon.style.background = 'var(--success)';
      icon.style.boxShadow = '0 0 0 1px var(--success)';
      icon.style.transform = 'scale(1.0)';
      icon.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
      label.style.color = 'var(--success)';
      label.style.fontWeight = '600';
    }
  };

  const handleSuccess = (res) => {
    // Hide active stage animations inside the icons
    document.querySelectorAll('.stage-icon div').forEach(div => div.remove());
    
    // Hide form fields and bottom modal footer
    document.getElementById('uploadModalForm').classList.add('hidden');
    const footer = document.querySelector('#uploadModal .modal-footer');
    if (footer) footer.classList.add('hidden');

    // Create and append the beautiful complete card
    const doneCard = document.createElement('div');
    doneCard.style.marginTop = '24px';
    doneCard.style.padding = '24px';
    doneCard.style.background = '#f0fdf4';
    doneCard.style.border = '1px solid #bbf7d0';
    doneCard.style.borderRadius = '16px';
    doneCard.style.display = 'flex';
    doneCard.style.flexDirection = 'column';
    doneCard.style.alignItems = 'center';
    doneCard.style.textAlign = 'center';
    doneCard.style.animation = 'scaleIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';
    
    doneCard.innerHTML = `
      <div style="width:56px;height:56px;border-radius:50%;background:var(--success);display:flex;align-items:center;justify-content:center;color:#fff;box-shadow:0 4px 12px rgba(16,185,129,0.2);margin-bottom:16px;">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
      <h3 style="font-weight:700;font-size:18px;color:#065f46;margin:0 0 4px 0">Upload & Ingestion Complete</h3>
      <p style="font-size:13px;color:#047857;margin:0 0 20px 0;line-height:1.4">Your document has been successfully parsed, split into vector chunks, and indexed in the knowledge base.</p>
      
      <div style="width:100%;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px 16px;display:flex;align-items:center;gap:12px;margin-bottom:24px;text-align:left;box-shadow:0 1px 3px rgba(0,0,0,0.02)">
        <div style="width:36px;height:36px;border-radius:8px;background:#f8fafc;border:1px solid #e2e8f0;display:flex;align-items:center;justify-content:center;color:var(--text-tertiary)">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </div>
        <div style="flex:1;overflow:hidden">
          <div style="font-weight:600;font-size:13px;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(res.document ? (res.document.title || res.document.file_name) : selectedFile.name)}</div>
          <div style="font-size:11px;color:var(--text-tertiary);margin-top:2px">${res.chunk_count || 0} chunks generated & indexed</div>
        </div>
      </div>
      
      <button class="btn btn-primary" onclick="closeUploadModal(); loadDocuments();" style="width:100%">Got it, thank you!</button>
    `;
    prog.appendChild(doneCard);
    showToast('Document successfully indexed in Knowledge Base', 'success');
  };

  const handleFailure = (err) => {
    showToast('Processing failed: ' + err.message, 'error');
    const activeIcon = document.querySelector(`#stage-${currentStageIdx} .stage-icon`);
    if (activeIcon) {
      activeIcon.style.background = 'var(--error)';
      activeIcon.style.boxShadow = '0 0 0 1px var(--error)';
      activeIcon.style.transform = 'scale(1.0)';
      activeIcon.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    }
  };

  // Set the first stage as active
  let currentStageIdx = 0;
  updateStageUI(0, 'active');

  let uploadCompleted = false;
  let uploadResult = null;
  let uploadError = null;

  // Smooth sequential progress interval (moves from left to right, going green)
  const advanceStageInterval = setInterval(() => {
    if (currentStageIdx < stages.length - 1) {
      // Mark current stage as complete (green)
      updateStageUI(currentStageIdx, 'complete');
      currentStageIdx++;
      // Activate next stage (blue pulsing)
      updateStageUI(currentStageIdx, 'active');
      // Extend connecting progress line
      const percentage = (currentStageIdx / (stages.length - 1)) * 100;
      const progressLine = document.getElementById('progressLine');
      if (progressLine) {
        progressLine.style.width = `${percentage}%`;
      }
    } else {
      // We are at the final stage ("Indexing").
      // Check if the API call has completed.
      if (uploadCompleted) {
        clearInterval(advanceStageInterval);
        if (uploadError) {
          handleFailure(uploadError);
        } else {
          updateStageUI(stages.length - 1, 'complete');
          const progressLine = document.getElementById('progressLine');
          if (progressLine) progressLine.style.width = '100%';
          handleSuccess(uploadResult);
        }
      }
    }
  }, 1100); // 1.1s per stage transitions for smooth eye-catching visual pacing

  // Fire off real RAG pipeline upload in parallel
  API.uploadDocument(
    selectedFile,
    document.getElementById('uploadTitle').value,
    '',
    document.getElementById('uploadTags').value
  ).then(res => {
    uploadResult = res;
    uploadCompleted = true;
    
    // If the progressive animation already reached the last stage, resolve instantly!
    if (currentStageIdx === stages.length - 1) {
      clearInterval(advanceStageInterval);
      updateStageUI(stages.length - 1, 'complete');
      const progressLine = document.getElementById('progressLine');
      if (progressLine) progressLine.style.width = '100%';
      handleSuccess(res);
    }
  }).catch(err => {
    uploadError = err;
    uploadCompleted = true;
    clearInterval(advanceStageInterval);
    handleFailure(err);
  });

  btn.disabled = false;
  btn.textContent = 'Upload & Process File';
}
