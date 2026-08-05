/* ═══════════════════════════════════════════════════════════════
   API Client — communicates with FastAPI backend
   ═══════════════════════════════════════════════════════════════ */
function resolveApiBase() {
  const override = localStorage.getItem('api_base');
  if (override) return override.replace(/\/$/, '');
  const host = window.location.hostname;
  const isLocal =
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '[::1]' ||
    window.location.protocol === 'file:';
  return isLocal ? 'http://127.0.0.1:8000' : '';
}

const API_BASE = resolveApiBase();

const API = {
  _token() { return localStorage.getItem('token') || ''; },

  apiBase() {
    return API_BASE || window.location.origin;
  },

  async _req(method, path, body, extra = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (this._token()) headers['Authorization'] = 'Bearer ' + this._token();
    Object.assign(headers, extra.headers || {});

    const opts = { method, headers };
    if (body && method !== 'GET') opts.body = JSON.stringify(body);

    const url = (API_BASE || '') + path;
    let res;
    try {
      res = await fetch(url, opts);
    } catch (networkErr) {
      const base = API_BASE || window.location.origin;
      throw new Error(
        `Cannot reach the API at ${base}. Start the backend in the project folder: ` +
          'uvicorn Backend.main:app --reload'
      );
    }
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = json.detail;
      const msg = Array.isArray(d) ? d.map((x) => x.msg || JSON.stringify(x)).join('; ')
        : (typeof d === 'string' ? d : d ? JSON.stringify(d) : `Request failed (${res.status})`);
      throw new Error(msg);
    }
    return json;
  },

  async healthCheck() {
    return this._req('GET', '/health');
  },

  async _upload(path, formData) {
    const headers = {};
    if (this._token()) headers['Authorization'] = 'Bearer ' + this._token();
    const url = (API_BASE || '') + path;
    let res;
    try {
      res = await fetch(url, { method: 'POST', headers, body: formData });
    } catch {
      throw new Error(
        `Cannot reach the API at ${API_BASE || window.location.origin}. Is uvicorn running?`
      );
    }
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.detail || 'Upload failed');
    return json;
  },

  // ── Auth ──────────────────────────────────────────────────
  register(full_name, email, password, organization_name) {
    return this._req('POST', '/auth/register', { email, password, full_name, organization_name });
  },
  registerPublic(full_name, email, password) {
    return this._req('POST', '/auth/register/public', { email, password, full_name });
  },
  login(email, password) {
    return this._req('POST', '/auth/login', { email, password });
  },
  subscribeToOrganizations(organization_ids) {
    return this._req('POST', '/users/subscribe', { organization_ids });
  },
  browseOrganizations(q = '') {
    const params = new URLSearchParams();
    if (q && q.trim()) params.set('q', q.trim());
    params.set('limit', '100');
    const qs = params.toString();
    return this._req('GET', `/orgs/browse${qs ? '?' + qs : ''}`);
  },
  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = 'index.html';
  },
  getUser() {
    try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; }
  },
  setUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
  },
  isLoggedIn() { return !!this._token(); },
  isPublicUser() {
    const u = this.getUser();
    return u.role === 'public_user';
  },
  getSubscribedOrgIds() {
    const u = this.getUser();
    return u.subscribed_org_ids || [];
  },

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
  uploadDocument(file, title, description, tags, status = 'private') {
    const fd = new FormData();
    fd.append('file', file);
    if (title) fd.append('title', title);
    if (description) fd.append('description', description);
    if (tags) fd.append('tags', tags);
    if (status) fd.append('status', status);
    return this._upload('/documents/upload', fd);
  },
  updateDocumentStatus(docId, status) {
    return this._req('PATCH', `/documents/${docId}/status`, { status });
  },
  deleteDocument(docId) {
    return this._req('DELETE', `/documents/${docId}`);
  },

  // ── Query ─────────────────────────────────────────────────
  askQuestion(question, top_k = 8, conversation_id = null, org_ids = null) {
    const body = { question, top_k, conversation_id };
    if (org_ids && org_ids.length) body.org_ids = org_ids;
    return this._req('POST', '/query/ask', body);
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

  // ── Voice ─────────────────────────────────────────────────
  generateVoice(text) {
    const url = (API_BASE || '') + '/voice/generate';
    const headers = { 'Content-Type': 'application/json' };
    if (this._token()) headers['Authorization'] = 'Bearer ' + this._token();
    return fetch(url, { method: 'POST', headers, body: JSON.stringify({ text }) })
      .then(res => {
        if (!res.ok) throw new Error("Voice generation failed");
        return res.blob();
      });
  },

  transcribeAudio(audioBlob) {
    const url = (API_BASE || '') + '/voice/transcribe';
    const headers = {};
    if (this._token()) headers['Authorization'] = 'Bearer ' + this._token();
    
    const formData = new FormData();
    formData.append('file', audioBlob, 'mic.wav');

    return fetch(url, { method: 'POST', headers, body: formData })
      .then(res => {
        if (!res.ok) throw new Error("Speech transcription failed");
        return res.json();
      });
  }
};
