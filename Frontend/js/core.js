/* ═══ Core App — Navigation, Sidebar, Toast, Command Palette ═══ */

// ── WebSocket Live-Reload Interceptor (Frontend-Only Dev-Server Bypass) ─────
(function() {
  const OriginalWebSocket = window.WebSocket;
  window.WebSocket = function(url, protocols) {
    const ws = new OriginalWebSocket(url, protocols);
    const originalAdd = ws.addEventListener;
    ws.addEventListener = function(type, listener, options) {
      if (type === 'message') {
        const originalListener = listener;
        listener = function(event) {
          if (event.data === 'reload' || (typeof event.data === 'string' && event.data.includes('reload'))) {
            const isUploading = document.getElementById('uploadProgress') && 
                                !document.getElementById('uploadProgress').classList.contains('hidden') && 
                                document.getElementById('uploadProgress').innerHTML !== '';
            if (isUploading) {
              console.warn('[Antigravity] Blocked live-server reload during active upload ingestion.');
              return;
            }
          }
          return originalListener.apply(this, arguments);
        };
      }
      return originalAdd.call(this, type, listener, options);
    };

    let userHandler = null;
    Object.defineProperty(ws, 'onmessage', {
      get() { return userHandler; },
      set(val) {
        userHandler = val;
        ws.removeEventListener('message', ws._customOnMessage);
        ws._customOnMessage = function(event) {
          if (event.data === 'reload' || (typeof event.data === 'string' && event.data.includes('reload'))) {
            const isUploading = document.getElementById('uploadProgress') && 
                                !document.getElementById('uploadProgress').classList.contains('hidden') && 
                                document.getElementById('uploadProgress').innerHTML !== '';
            if (isUploading) {
              console.warn('[Antigravity] Blocked live-server reload during active upload ingestion.');
              return;
            }
          }
          if (userHandler) userHandler.call(ws, event);
        };
        ws.addEventListener('message', ws._customOnMessage);
      }
    });
    return ws;
  };
  window.WebSocket.prototype = OriginalWebSocket.prototype;
})();

if (!API.isLoggedIn()) window.location.href = 'index.html';

// ── State ───────────────────────────────────────────────────
let currentPage = 'chat';
let chatHistory = [];
let selectedFile = null;

// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const user = API.getUser();
  document.getElementById('userName').textContent = user.full_name || 'User';
  document.getElementById('userAvatar').textContent = (user.full_name || 'U')[0].toUpperCase();
  loadOrgName();
  navigate('chat');
  setupKeyboardShortcuts();
  buildCommandList();
  if (window.innerWidth <= 768) document.getElementById('mobileMenuBtn').style.display = 'block';
});

async function loadOrgName() {
  try {
    const org = await API.getOrganization();
    document.getElementById('userOrg').textContent = org.name || 'Organization';
  } catch { document.getElementById('userOrg').textContent = 'My Workspace'; }
}

// ── Navigation ──────────────────────────────────────────────
const pageNames = { chat:'Ask AI', documents:'Documents', analytics:'Analytics', history:'Query History', org:'Organization', team:'Team Members', admin:'Settings' };

function navigate(page) {
  currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
  document.getElementById('page-' + page).classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  document.getElementById('breadcrumbPage').textContent = pageNames[page] || page;

  if (page === 'chat') loadChatPage();
  else if (page === 'documents') loadDocuments();
  else if (page === 'analytics') loadAnalytics();
  else if (page === 'history') loadHistory();
  else if (page === 'org') loadOrg();
  else if (page === 'team') loadTeam();
  else if (page === 'admin') renderAdminTab('general');
  if (window.innerWidth <= 768) toggleMobileSidebar(false);
}

// ── Sidebar ─────────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('collapsed');
}
function toggleMobileSidebar(open) {
  const sb = document.getElementById('sidebar');
  const ov = document.getElementById('mobileSidebarOverlay');
  const isOpen = open !== undefined ? open : !sb.classList.contains('open');
  sb.classList.toggle('open', isOpen);
  ov.classList.toggle('active', isOpen);
}

// ── Toast ───────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const icons = {
    success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
    error: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  };
  const el = document.createElement('div');
  el.className = 'toast toast-' + type;
  el.innerHTML = '<span class="toast-icon">' + (icons[type]||icons.info) + '</span><span>' + msg + '</span>';
  c.appendChild(el);
  setTimeout(() => { el.style.animation = 'toast-out .3s forwards'; setTimeout(() => el.remove(), 300); }, 3500);
}

// ── Command Palette ─────────────────────────────────────────
const commands = [
  { label: 'Ask AI', page: 'chat', key: '1' },
  { label: 'Documents', page: 'documents', key: '2' },
  { label: 'Analytics', page: 'analytics', key: '3' },
  { label: 'Query History', page: 'history', key: '4' },
  { label: 'Organization', page: 'org', key: '5' },
  { label: 'Settings', page: 'admin', key: '6' },
  { label: 'Upload Document', action: () => { navigate('documents'); openUploadModal(); } },
  { label: 'Sign Out', action: () => API.logout() },
];

function buildCommandList(filter = '') {
  const list = document.getElementById('cmdList');
  const f = filter.toLowerCase();
  const filtered = commands.filter(c => c.label.toLowerCase().includes(f));
  list.innerHTML = filtered.map((c, i) =>
    `<div class="cmd-item${i===0?' active':''}" onclick="${c.page ? `navigate('${c.page}');closeCommandPalette()` : ''}" data-idx="${i}">
      <span>${c.label}</span>
      ${c.key ? `<span class="cmd-item-key">${c.key}</span>` : ''}
    </div>`
  ).join('');
  // Attach action handlers
  filtered.forEach((c, i) => {
    if (c.action) list.children[i].onclick = () => { c.action(); closeCommandPalette(); };
  });
}
function filterCommands(val) { buildCommandList(val); }
function openCommandPalette() {
  document.getElementById('cmdPalette').classList.remove('hidden');
  const inp = document.getElementById('cmdInput');
  inp.value = '';
  inp.focus();
  buildCommandList();
}
function closeCommandPalette() { document.getElementById('cmdPalette').classList.add('hidden'); }

function setupKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); openCommandPalette(); }
    if (e.key === 'Escape') closeCommandPalette();
  });
}

// ── Utility ─────────────────────────────────────────────────
function timeAgo(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  return Math.floor(hrs / 24) + 'd ago';
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function formatMarkdown(text) {
  if (!text) return '';
  let h = escapeHtml(text);
  // Code blocks
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  // Inline code
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Newlines to paragraphs
  h = h.split('\n\n').map(p => '<p>' + p.replace(/\n/g, '<br>') + '</p>').join('');
  return h;
}

function categoryColor(cat) {
  const map = { academic:'purple', finance:'green', hostel:'yellow', administration:'red', general:'default', error:'red', unknown:'default' };
  return map[cat] || 'default';
}
