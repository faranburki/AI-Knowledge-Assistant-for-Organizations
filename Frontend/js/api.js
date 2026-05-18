/* ═══════════════════════════════════════════════════════════════
   API Client — communicates with FastAPI backend
   ═══════════════════════════════════════════════════════════════ */
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:')
  ? 'http://127.0.0.1:8000'
  : '';          // same-origin in production

const API = {
  _token() { return localStorage.getItem('token') || ''; },

  async _req(method, path, body, extra = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (this._token()) headers['Authorization'] = 'Bearer ' + this._token();
    Object.assign(headers, extra.headers || {});

    const opts = { method, headers };
    if (body && method !== 'GET') opts.body = JSON.stringify(body);

    const res = await fetch(API_BASE + path, opts);
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.detail || `Request failed (${res.status})`);
    return json;
  },

  async _upload(path, formData) {
    const headers = {};
    if (this._token()) headers['Authorization'] = 'Bearer ' + this._token();
    const res = await fetch(API_BASE + path, { method: 'POST', headers, body: formData });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.detail || 'Upload failed');
    return json;
  },

  // ── Auth ──────────────────────────────────────────────────
  register(full_name, email, password, organization_name) {
    return this._req('POST', '/auth/register', { email, password, full_name, organization_name });
  },
  login(email, password) {
    return this._req('POST', '/auth/login', { email, password });
  },
  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = 'index.html';
  },
  getUser() {
    try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; }
  },
  isLoggedIn() { return !!this._token(); },

  // ── Organization ──────────────────────────────────────────
  getOrganization() { return this._req('GET', '/orgs/me'); },
  createOrganization(name, description) {
    return this._req('POST', '/orgs/create', { name, description });
  },
  listOrgUsers() { return this._req('GET', '/orgs/users'); },
  createOrgUser(email, password, full_name, is_admin) {
    return this._req('POST', '/orgs/users', { email, password, full_name, is_admin });
  },

  // ── Documents ─────────────────────────────────────────────
  listDocuments(limit = 50, skip = 0) {
    return this._req('GET', `/documents/list?limit=${limit}&skip=${skip}`);
  },
  uploadDocument(file, title, description, tags) {
    const fd = new FormData();
    fd.append('file', file);
    if (title) fd.append('title', title);
    if (description) fd.append('description', description);
    if (tags) fd.append('tags', tags);
    return this._upload('/documents/upload', fd);
  },
  deleteDocument(docId) {
    return this._req('DELETE', `/documents/${docId}`);
  },

  // ── Query ─────────────────────────────────────────────────
  askQuestion(question, top_k = 8, conversation_id = null) {
    return this._req('POST', '/query/ask', { question, top_k, conversation_id });
  },
  getConversation(conversationId) {
    return this._req('GET', `/query/conversation/${conversationId}`);
  },
  getQueryHistory(limit = 30) {
    return this._req('GET', `/query/history?limit=${limit}`);
  },
  deleteQuery(queryId) {
    return this._req('DELETE', `/query/${queryId}`);
  },
  getAnalytics() {
    return this._req('GET', '/query/analytics');
  },

  // ── Health ────────────────────────────────────────────────
  health() { return this._req('GET', '/health'); },
};
