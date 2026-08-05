export function resolveApiBase() {
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

export const API_BASE = resolveApiBase();

export function getToken() {
  return localStorage.getItem('token') || '';
}

export function getUser() {
  try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; }
}

export function isLoggedIn() {
  return !!getToken();
}

export async function request(method, path, body = null, extra = {}) {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;
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
}

export async function upload(path, formData) {
  const headers = {};
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const url = (API_BASE || '') + path;
  let res;
  try {
    res = await fetch(url, { method: 'POST', headers, body: formData });
  } catch {
    throw new Error(`Cannot reach the API at ${API_BASE || window.location.origin}. Is uvicorn running?`);
  }
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || 'Upload failed');
  return json;
}
