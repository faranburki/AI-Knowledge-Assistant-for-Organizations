/* ═══ Chat Page Logic ═══ */

let isStreaming = false;

function startNewChat() {
  chatHistory = [];
  window.activeQueryId = null;
  window.activeConversationId = null;
  const msgs = document.getElementById('chatMessages');
  msgs.innerHTML = '';
  renderChatEmpty();
  document.getElementById('chatInput').value = '';
  document.getElementById('chatInput').focus();
  
  // Clear active sidebar selections
  document.querySelectorAll('.chat-list-item').forEach(el => el.classList.remove('active'));
}

function renderChatEmpty() {
  document.getElementById('chatMessages').innerHTML = `
    <div class="empty-state" id="chatEmpty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:48px;height:48px;color:var(--text-tertiary);margin-bottom:16px"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      <h3>Ask anything about your documents</h3>
      <p style="font-size:var(--text-sm);color:var(--text-secondary);max-width:320px">Your AI assistant uses RAG to find answers from uploaded organizational knowledge.</p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:20px;justify-content:center">
        <button class="btn btn-secondary btn-sm" onclick="setQuestion('What is the fee structure?')">Fee structure</button>
        <button class="btn btn-secondary btn-sm" onclick="setQuestion('What are the hostel rules?')">Hostel rules</button>
        <button class="btn btn-secondary btn-sm" onclick="setQuestion('How do I apply for a scholarship?')">Scholarships</button>
      </div>
    </div>`;
}

function setQuestion(q) {
  document.getElementById('chatInput').value = q;
  document.getElementById('chatSendBtn').disabled = false;
  document.getElementById('chatInput').focus();
}

function handleChatKey(e) {
  const btn = document.getElementById('chatSendBtn');
  btn.disabled = !e.target.value.trim();
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (e.target.value.trim()) sendQuestion(); }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

async function sendQuestion() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question || isStreaming) return;
  
  window.activeQueryId = null;

  // Clear empty state
  const empty = document.getElementById('chatEmpty');
  if (empty) empty.remove();

  // Add user message
  appendMessage('user', question);
  chatHistory.push({ role: 'user', content: question });
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('chatSendBtn').disabled = true;

  // Show typing indicator
  const typingEl = showTyping();
  isStreaming = true;

  try {
    const result = await API.askQuestion(question, 8, window.activeConversationId || null);
    window.activeConversationId = result.conversation_id;
    typingEl.remove();

    const sourceChips = (result.sources || []).map(s =>
      `<button class="source-chip" title="${escapeHtml(s.excerpt || '')}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        ${escapeHtml(s.source_name || 'Source')}
      </button>`
    ).join('');

    const catBadge = result.category
      ? `<span class="badge badge-${categoryColor(result.category)}" style="font-size:11px;font-weight:600">${result.category}</span>`
      : '';

    const confidenceVal = result.confidence || 0;
    const confidenceHtml = confidenceVal > 0 ? `
      <span style="display:inline-flex;align-items:center;gap:4px">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        Confidence: ${Math.round(confidenceVal * 100)}%
      </span>
    ` : '';

    const extra = `
      <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border-primary)">
        ${sourceChips ? `<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">${sourceChips}</div>` : ''}
        ${sourceChips && (catBadge || confidenceHtml) ? '<div style="width:1px;height:14px;background:var(--border-primary)"></div>' : ''}
        <div style="display:flex;align-items:center;gap:12px;color:var(--text-tertiary);font-size:12px;font-weight:500">
          ${catBadge}
          <span style="display:inline-flex;align-items:center;gap:4px">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
            ${result.response_time_ms || 0}ms
          </span>
          ${confidenceHtml}
        </div>
      </div>
    `;

    appendMessage('assistant', result.answer, extra);
    chatHistory.push({ role: 'assistant', content: result.answer });
    await loadChatPage();
  } catch (err) {
    typingEl.remove();
    appendMessage('assistant', 'Sorry, something went wrong: ' + (err.message || 'Unknown error'));
  }
  isStreaming = false;
  input.focus();
}

function appendMessage(role, content, extra = '') {
  const msgs = document.getElementById('chatMessages');
  const user = API.getUser();
  const avatar = role === 'user' ? (user.full_name || 'U')[0] : 'AI';
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.innerHTML = `
    <div class="msg-avatar-wrap">
      <div class="msg-avatar">${avatar}</div>
    </div>
    <div class="msg-content">
      <div class="msg-header">
        <span class="fw-medium" style="color:var(--text-primary)">${role === 'user' ? (user.full_name || 'You') : 'AI Assistant'}</span>
        <span style="font-size:11px;color:var(--text-tertiary);margin-left:4px">${time}</span>
      </div>
      <div class="msg-body">${formatMarkdown(content)}</div>
      ${extra}
    </div>`;
  msgs.appendChild(div);
  msgs.scrollTo({ top: msgs.scrollHeight, behavior: 'smooth' });
}

function showTyping() {
  const msgs = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg assistant';
  div.innerHTML = `
    <div class="msg-avatar-wrap">
      <div class="msg-avatar">AI</div>
    </div>
    <div class="msg-content">
      <div class="msg-header">
        <span class="fw-medium" style="color:var(--text-primary)">AI Assistant</span>
      </div>
      <div class="typing-indicator"><span></span><span></span><span></span></div>
    </div>`;
  msgs.appendChild(div);
  msgs.scrollTo({ top: msgs.scrollHeight, behavior: 'smooth' });
  return div;
}

async function loadChatPage() {
  const list = document.getElementById('chatList');
  list.innerHTML = '<div style="padding:16px;text-align:center"><div class="spinner" style="width:18px;height:18px;border-width:2px;margin:0 auto"></div></div>';
  try {
    const items = await API.getQueryHistory(20);
    if (!items || !items.length) {
      list.innerHTML = '<div style="padding:16px;text-align:center;font-size:12px;color:var(--text-tertiary)">No recent conversations</div>';
      return;
    }
    
    list.innerHTML = items.map((q, idx) => `
      <div class="chat-list-item" onclick="selectHistoryItem(${idx})" id="history-item-${q.query_id}" style="cursor:pointer; position:relative; padding-right:40px;">
        <div class="chat-title" style="font-weight:600;font-size:13px;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(q.question)}</div>
        <div class="chat-preview" style="font-size:12px;color:var(--text-tertiary);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(q.answer)}</div>
        <div class="chat-time" style="font-size:10px;color:var(--text-tertiary);margin-top:4px">${timeAgo(q.timestamp)}</div>
        
        <!-- Hover Delete Icon Button -->
        <button class="delete-chat-btn" onclick="deleteChatLog('${q.query_id}', event)" title="Delete conversation" style="position:absolute; right:12px; top:50%; transform:translateY(-50%); background:none; border:none; color:var(--text-tertiary); padding:6px; border-radius:6px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition: all 0.2s; opacity:0; pointer-events:auto;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
        </button>
      </div>
    `).join('');
    
    window.historyItems = items;
    
    // Maintain active highlighting
    if (window.activeConversationId) {
      const act = document.getElementById('history-item-' + window.activeConversationId);
      if (act) act.classList.add('active');
    }
  } catch (err) {
    list.innerHTML = '<div style="padding:16px;text-align:center;font-size:12px;color:var(--error)">Failed to load history</div>';
  }
}

async function selectHistoryItem(idx) {
  const item = window.historyItems[idx];
  if (!item) return;
  
  window.activeConversationId = item.query_id;
  window.activeQueryId = null;
  
  // Set active styling
  document.querySelectorAll('.chat-list-item').forEach(el => el.classList.remove('active'));
  const activeEl = document.getElementById('history-item-' + item.query_id);
  if (activeEl) activeEl.classList.add('active');
  
  // Clear chat pane and show loading state
  const msgs = document.getElementById('chatMessages');
  msgs.innerHTML = '<div style="padding:40px;text-align:center"><div class="spinner" style="margin:0 auto"></div></div>';
  
  try {
    const messages = await API.getConversation(item.query_id);
    msgs.innerHTML = '';
    chatHistory = [];
    
    if (!messages || !messages.length) {
      renderChatEmpty();
      return;
    }
    
    messages.forEach(msg => {
      // Append user turn
      appendMessage('user', msg.question);
      chatHistory.push({ role: 'user', content: msg.question });
      
      // Append assistant turn
      const sourceChips = (msg.sources || []).map(s =>
        `<button class="source-chip" title="${escapeHtml(s.excerpt || '')}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          ${escapeHtml(s.source_name || 'Source')}
        </button>`
      ).join('');

      const catBadge = msg.category
        ? `<span class="badge badge-${categoryColor(msg.category)}" style="font-size:11px;font-weight:600">${msg.category}</span>`
        : '';

      const extra = `
        <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border-primary)">
          ${sourceChips ? `<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">${sourceChips}</div>` : ''}
          ${sourceChips && catBadge ? '<div style="width:1px;height:14px;background:var(--border-primary)"></div>' : ''}
          <div style="display:flex;align-items:center;gap:12px;color:var(--text-tertiary);font-size:12px;font-weight:500">
            ${catBadge}
            <span style="display:inline-flex;align-items:center;gap:4px">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
              ${msg.response_time_ms || 0}ms
            </span>
          </div>
        </div>
      `;
      appendMessage('assistant', msg.answer, extra);
      chatHistory.push({ role: 'assistant', content: msg.answer });
    });
  } catch (err) {
    msgs.innerHTML = `<div style="padding:40px;text-align:center;color:var(--error)">Failed to load messages: ${err.message}</div>`;
  }
}

function deleteChatLog(queryId, event) {
  if (event) event.stopPropagation();
  window.queryIdToDelete = queryId;
  const modal = document.getElementById('deleteConfirmModal');
  if (modal) modal.classList.remove('hidden');
}

function closeDeleteModal(event) {
  if (event && event.stopPropagation) event.stopPropagation();
  const modal = document.getElementById('deleteConfirmModal');
  if (modal) modal.classList.add('hidden');
  window.queryIdToDelete = null;
}

async function performDeleteChat() {
  const queryId = window.queryIdToDelete;
  if (!queryId) return;
  
  const confirmBtn = document.getElementById('confirmDeleteBtn');
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;border-top-color:#fff;margin:0 auto"></div>';
  }
  
  const itemEl = document.getElementById('history-item-' + queryId);
  if (itemEl) {
    itemEl.classList.add('deleting');
  }
  
  // Close confirmation modal immediately to feel ultra-responsive
  closeDeleteModal();
  
  try {
    // Delete in background
    await API.deleteQuery(queryId);
    showToast("Conversation deleted successfully", "success");
    
    // If we just deleted the active chat, reset to a fresh chat
    if (window.activeConversationId === queryId) {
      startNewChat();
    }
    
    // Wait for the slide-out and collapse height animation to finish
    setTimeout(() => {
      if (itemEl) itemEl.remove();
      
      // Update memory array
      if (window.historyItems) {
        window.historyItems = window.historyItems.filter(item => item.query_id !== queryId);
        
        // Show empty placeholder if no items are left
        if (!window.historyItems.length) {
          const list = document.getElementById('chatList');
          if (list) {
            list.innerHTML = '<div style="padding:16px;text-align:center;font-size:12px;color:var(--text-tertiary)">No recent conversations</div>';
          }
        }
      }
    }, 400);
  } catch (err) {
    // If deletion fails, reverse animation to restore item smoothly
    if (itemEl) {
      itemEl.classList.remove('deleting');
    }
    showToast("Failed to delete conversation: " + err.message, "error");
  } finally {
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.innerText = 'Delete conversation';
    }
  }
}

function toggleChatSidebar() {
  const sidebar = document.getElementById('chatSidebar');
  if (sidebar) {
    sidebar.classList.toggle('collapsed');
  }
}
