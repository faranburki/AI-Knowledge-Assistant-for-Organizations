/**
 * history.js — Renders query history table with search, filter, and pagination
 * DocuMind AI Frontend
 *
 * Backend integration note:
 *   Replace `QUERY_HISTORY` with a fetch() call to GET /api/history
 *   and populate the same `renderTable()` function with the response.
 */

/* ── Page loader ──────────────────────────────────────── */
window.addEventListener('load', () => {
  const loader = document.getElementById('pageLoader');
  if (loader) setTimeout(() => loader.classList.add('hidden'), 300);
  init();
});

/* ── Dummy query history data ─────────────────────────── */
const QUERY_HISTORY = [
  { id: 1,  query: 'How to apply for hostel accommodation?',     category: 'Hostel',   date: '2026-03-01', time: '09:12 AM', responseMs: 820,  rating: 5 },
  { id: 2,  query: 'Fee payment method for semester',            category: 'Finance',  date: '2026-03-02', time: '10:45 AM', responseMs: 650,  rating: 4 },
  { id: 3,  query: 'What is the attendance policy?',             category: 'Academic', date: '2026-03-03', time: '11:22 AM', responseMs: 710,  rating: 5 },
  { id: 4,  query: 'Library hours on weekends',                  category: 'Library',  date: '2026-03-04', time: '02:15 PM', responseMs: 540,  rating: 4 },
  { id: 5,  query: 'How to reset my student portal password?',   category: 'IT',       date: '2026-03-05', time: '03:08 PM', responseMs: 920,  rating: 3 },
  { id: 6,  query: 'When is the mid-term exam schedule released?', category: 'Academic', date: '2026-03-06', time: '08:55 AM', responseMs: 880,  rating: 5 },
  { id: 7,  query: 'Documents required for hostel check-in',     category: 'Hostel',   date: '2026-03-06', time: '11:30 AM', responseMs: 760,  rating: 4 },
  { id: 8,  query: 'Can I pay fees in installments?',            category: 'Finance',  date: '2026-03-07', time: '09:41 AM', responseMs: 590,  rating: 5 },
  { id: 9,  query: 'What is the grading system used?',           category: 'Academic', date: '2026-03-07', time: '01:20 PM', responseMs: 670,  rating: 4 },
  { id: 10, query: 'Health insurance coverage for students',     category: 'Health',   date: '2026-03-08', time: '10:05 AM', responseMs: 810,  rating: 3 },
  { id: 11, query: 'How to get a student ID card replacement?',  category: 'IT',       date: '2026-03-08', time: '02:48 PM', responseMs: 730,  rating: 5 },
  { id: 12, query: 'Scholarship application deadlines',          category: 'Finance',  date: '2026-03-09', time: '09:22 AM', responseMs: 640,  rating: 4 },
  { id: 13, query: 'Can I extend my library book borrowing?',    category: 'Library',  date: '2026-03-09', time: '11:10 AM', responseMs: 510,  rating: 5 },
  { id: 14, query: 'Rules for using university gym facilities',  category: 'Hostel',   date: '2026-03-10', time: '04:30 PM', responseMs: 860,  rating: 4 },
  { id: 15, query: 'How to apply for course withdrawal?',        category: 'Academic', date: '2026-03-10', time: '03:15 PM', responseMs: 720,  rating: 3 },
  { id: 16, query: 'Late fee penalty amount',                    category: 'Finance',  date: '2026-03-11', time: '08:44 AM', responseMs: 480,  rating: 5 },
  { id: 17, query: 'WiFi access in hostel rooms',                category: 'IT',       date: '2026-03-11', time: '10:58 AM', responseMs: 610,  rating: 4 },
  { id: 18, query: 'Vaccination requirements for hostels',       category: 'Health',   date: '2026-03-11', time: '01:35 PM', responseMs: 750,  rating: 4 },
];

/* ── Pagination config ────────────────────────────────── */
const PAGE_SIZE = 8;
let currentPage = 1;
let filteredData = [...QUERY_HISTORY];

/* ── Category color map ───────────────────────────────── */
const CAT_CLASSES = {
  Hostel:   'cat-hostel',
  Finance:  'cat-finance',
  Academic: 'cat-academic',
  Library:  'cat-academic',  // reuse blue
  IT:       'cat-finance',   // amber
  Health:   'cat-hostel',    // purple
};

/* ── Render star rating ───────────────────────────────── */
function renderStars(n) {
  return Array.from({ length: 5 }, (_, i) =>
    `<span style="color:${i < n ? '#f59e0b' : '#e5e7eb'};font-size:.85rem;">★</span>`
  ).join('');
}

/* ── Render stats strip ───────────────────────────────── */
function renderStats() {
  const statsRow = document.getElementById('statsRow');
  const total    = QUERY_HISTORY.length;
  const avgTime  = Math.round(QUERY_HISTORY.reduce((s, r) => s + r.responseMs, 0) / total);
  const avgRating = (QUERY_HISTORY.reduce((s, r) => s + r.rating, 0) / total).toFixed(1);
  const categories = new Set(QUERY_HISTORY.map(r => r.category)).size;

  const stats = [
    { val: total,           label: 'Total queries',    icon: '💬' },
    { val: `${avgTime}ms`,  label: 'Avg response time',icon: '⚡' },
    { val: `${avgRating}★`, label: 'Avg satisfaction', icon: '😊' },
    { val: categories,      label: 'Categories',       icon: '📂' },
  ];

  statsRow.innerHTML = stats.map(s => `
    <div class="card-custom" style="padding:18px 20px;display:flex;align-items:center;gap:14px;">
      <div style="font-size:1.4rem;">${s.icon}</div>
      <div>
        <div style="font-family:var(--font-display);font-size:1.35rem;font-weight:700;color:var(--primary);">${s.val}</div>
        <div style="font-size:.75rem;color:var(--text-muted);">${s.label}</div>
      </div>
    </div>
  `).join('');
}

/* ── Render table rows ────────────────────────────────── */
function renderTable() {
  const tbody    = document.getElementById('historyTableBody');
  const rowCount = document.getElementById('rowCount');
  const pageInfo = document.getElementById('pageInfo');

  const start = (currentPage - 1) * PAGE_SIZE;
  const end   = start + PAGE_SIZE;
  const page  = filteredData.slice(start, end);
  const total = filteredData.length;

  rowCount.textContent = `${total} result${total !== 1 ? 's' : ''}`;
  pageInfo.textContent = total === 0 ? '' :
    `Showing ${start + 1}–${Math.min(end, total)} of ${total}`;

  tbody.innerHTML = '';

  if (page.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <h5>No results found</h5>
            <p>Try a different search term or category</p>
          </div>
        </td>
      </tr>`;
    renderPagination(0);
    return;
  }

  page.forEach((row, i) => {
    const catCls = CAT_CLASSES[row.category] || 'cat-default';
    const tr = document.createElement('tr');
    tr.style.animationDelay = `${i * 0.04}s`;
    tr.style.animation = 'msgIn .3s ease both';
    tr.innerHTML = `
      <td style="color:var(--text-muted);font-size:.8rem;">${row.id}</td>
      <td>
        <div style="font-weight:500;font-size:.875rem;color:var(--text-heading);max-width:360px;">${row.query}</div>
        <div style="font-size:.75rem;color:var(--text-muted);margin-top:2px;">${row.time}</div>
      </td>
      <td><span class="cat-badge ${catCls}">${row.category}</span></td>
      <td style="color:var(--text-muted);font-size:.85rem;white-space:nowrap;">${row.date}</td>
      <td style="color:var(--text-muted);font-size:.85rem;">${row.responseMs} ms</td>
      <td>${renderStars(row.rating)}</td>
      <td>
        <button class="btn-secondary-custom replay-btn" data-query="${encodeURIComponent(row.query)}"
          style="padding:5px 10px;font-size:.75rem;" title="Ask again">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Replay button: redirect to chat with query pre-filled
  document.querySelectorAll('.replay-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = decodeURIComponent(btn.dataset.query);
      sessionStorage.setItem('dm_preload_query', q);
      window.location.href = 'chat.html';
    });
  });

  renderPagination(total);
}

/* ── Render pagination buttons ────────────────────────── */
function renderPagination(total) {
  const container  = document.getElementById('pageButtons');
  const totalPages = Math.ceil(total / PAGE_SIZE);
  container.innerHTML = '';

  if (totalPages <= 1) return;

  const makeBtn = (label, page, disabled = false, active = false) => {
    const btn = document.createElement('button');
    btn.innerHTML = label;
    btn.disabled  = disabled;
    btn.className = 'btn-secondary-custom';
    btn.style.cssText = `padding:6px 12px;font-size:.8rem;${active ? 'background:var(--primary-light);color:var(--primary);border-color:var(--primary);font-weight:700;' : ''}`;
    if (!disabled) btn.addEventListener('click', () => {
      currentPage = page;
      renderTable();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    return btn;
  };

  container.appendChild(makeBtn('← Prev', currentPage - 1, currentPage === 1));

  for (let p = 1; p <= totalPages; p++) {
    container.appendChild(makeBtn(p, p, false, p === currentPage));
  }

  container.appendChild(makeBtn('Next →', currentPage + 1, currentPage === totalPages));
}

/* ── Search & filter ──────────────────────────────────── */
function applyFilters() {
  const search = document.getElementById('searchInput').value.trim().toLowerCase();
  const cat    = document.getElementById('categoryFilter').value;

  filteredData = QUERY_HISTORY.filter(row => {
    const matchSearch = !search || row.query.toLowerCase().includes(search);
    const matchCat    = !cat    || row.category === cat;
    return matchSearch && matchCat;
  });

  currentPage = 1;
  renderTable();
}

document.getElementById('searchInput').addEventListener('input', applyFilters);
document.getElementById('categoryFilter').addEventListener('change', applyFilters);

/* ── Export (fake CSV) ────────────────────────────────── */
document.getElementById('exportBtn').addEventListener('click', () => {
  const header = ['#', 'Query', 'Category', 'Date', 'Response Time (ms)', 'Rating'];
  const rows   = filteredData.map(r => [r.id, `"${r.query}"`, r.category, r.date, r.responseMs, r.rating]);
  const csv    = [header, ...rows].map(r => r.join(',')).join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `documind-history-${new Date().toISOString().split('T')[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);
});

/* ── Toast notification (shared utility) ──────────────── */
function showToast(type, title, message) {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast-custom toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">
      ${type === 'success'
        ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`
        : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`}
    </div>
    <div class="toast-text"><h6>${title}</h6><p>${message}</p></div>
  `;
  container.appendChild(toast);
  setTimeout(() => { toast.classList.add('hide'); setTimeout(() => toast.remove(), 350); }, 3500);
}

/* ── Init ─────────────────────────────────────────────── */
function init() {
  renderStats();
  renderTable();
}
