/* ═══ Analytics, History, Org, Admin Pages ═══ */

// ── Analytics ───────────────────────────────────────────────
async function loadAnalytics() {
  const stats = document.getElementById('analyticsStats');
  const chartsGrid = document.getElementById('chartsGrid');
  
  const user = API.getUser();
  const isAdmin = user && user.is_admin;

  if (isAdmin) {
    stats.style.display = 'grid';
    if (chartsGrid) {
      chartsGrid.style.gridTemplateColumns = '1fr 1fr';
      const recentChartCard = chartsGrid.querySelector('.chart-card:last-child');
      if (recentChartCard) recentChartCard.style.display = 'block';
    }
  } else {
    stats.style.display = 'none';
    if (chartsGrid) {
      chartsGrid.style.gridTemplateColumns = '1fr';
      const recentChartCard = chartsGrid.querySelector('.chart-card:last-child');
      if (recentChartCard) recentChartCard.style.display = 'none';
    }
  }

  stats.innerHTML = `<div class="stat-card"><div class="skeleton" style="height:60px"></div></div>`.repeat(4);

  try {
    const data = await API.getAnalytics();
    const cats = data.category_breakdown || {};
    const topCat = Object.entries(cats).sort((a, b) => b[1] - a[1])[0];

    if (isAdmin) {
      stats.innerHTML = `
        <div class="stat-card">
          <div class="stat-label">Total Queries</div>
          <div class="stat-value">${data.total_queries || 0}</div>
          <div class="stat-change text-success"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg> +12% this week</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Avg Response Time</div>
          <div class="stat-value">${Math.round(data.avg_response_time_ms || 0)}<span style="font-size:16px;font-weight:500;color:var(--text-tertiary);margin-left:4px">ms</span></div>
          <div class="stat-change text-success"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg> -5% faster</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Active Categories</div>
          <div class="stat-value">${Object.keys(cats).length}</div>
          <div class="stat-change" style="color:var(--text-tertiary)">Across all departments</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Top Category</div>
          <div class="stat-value" style="font-size:24px">${topCat ? topCat[0] : '—'}</div>
          ${topCat ? `<div class="stat-change text-accent">${topCat[1]} queries total</div>` : ''}
        </div>`;
    }

    drawCategoryChart(cats);
  } catch (err) {
    if (isAdmin) {
      stats.innerHTML = `<div class="stat-card" style="grid-column:1/-1"><p class="text-error" style="font-size:14px;display:flex;align-items:center;gap:8px"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> Failed to load analytics: ${err.message}</p></div>`;
    } else {
      showToast('Failed to load category distribution chart: ' + err.message, 'error');
    }
  }
}

function drawCategoryChart(cats) {
  const canvas = document.getElementById('catChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const entries = Object.entries(cats).sort((a, b) => b[1] - a[1]);
  if (!entries.length) { ctx.font = '13px Inter'; ctx.fillStyle = '#9ca3af'; ctx.fillText('No data yet', 20, 40); return; }

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 240 * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = '240px';
  ctx.scale(dpr, dpr);

  const w = rect.width, h = 240;
  const colors = ['#2563eb', '#059669', '#d97706', '#7c3aed', '#dc2626', '#475569'];
  const barW = Math.min(60, (w - 60) / entries.length - 16);
  const maxVal = Math.max(...entries.map(e => e[1]));

  // Draw grid lines
  ctx.strokeStyle = '#f1f5f9';
  ctx.lineWidth = 1;
  ctx.beginPath();
  [0, 0.5, 1].forEach(ratio => {
    const y = 40 + (h - 80) * ratio;
    ctx.moveTo(20, y);
    ctx.lineTo(w - 20, y);
  });
  ctx.stroke();

  entries.forEach(([cat, count], i) => {
    const x = 40 + i * (barW + 20);
    const barH = maxVal > 0 ? (count / maxVal) * (h - 90) : 0;
    const y = h - 40 - barH;

    // Bar background
    ctx.fillStyle = '#f8fafc';
    ctx.beginPath();
    ctx.roundRect(x, 40, barW, h - 80, 4);
    ctx.fill();

    // Actual bar
    ctx.fillStyle = colors[i % colors.length];
    ctx.beginPath();
    ctx.roundRect(x, y, barW, barH, 4);
    ctx.fill();

    // Label
    ctx.fillStyle = '#64748b';
    ctx.font = '12px Inter';
    ctx.textAlign = 'center';
    ctx.fillText(cat.length > 10 ? cat.substring(0,8)+'…' : cat, x + barW / 2, h - 16);
    
    // Value
    ctx.fillStyle = '#0f172a';
    ctx.font = 'bold 13px Inter';
    ctx.fillText(count, x + barW / 2, y - 8);
  });
}

// ── Query History ───────────────────────────────────────────
async function loadHistory() {
  const el = document.getElementById('historyTable');
  el.innerHTML = '<div style="padding:60px;text-align:center"><div class="spinner" style="margin:0 auto"></div></div>';

  try {
    const items = await API.getQueryHistory(50);
    if (!items || !items.length) {
      el.innerHTML = '<div class="empty-state"><div style="width:48px;height:48px;background:var(--bg-secondary);border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:16px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:24px;height:24px;color:var(--text-tertiary)"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div><h3 style="font-size:18px">No history found</h3><p style="color:var(--text-secondary)">Your organization hasn\'t asked any questions yet.</p></div>';
      return;
    }
    el.innerHTML = `<div class="table-responsive"><div class="table-wrap" style="box-shadow:0 2px 8px rgba(0,0,0,0.02)"><table class="table">
      <thead><tr><th>Question & Answer Preview</th><th>Category</th><th>Performance</th><th>Date</th></tr></thead>
      <tbody>${items.map(q => `<tr>
        <td style="max-width:500px">
          <div style="font-weight:600;font-size:14px;color:var(--text-primary);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(q.question)}</div>
          <div style="font-size:13px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml((q.answer || '').substring(0, 120))}…</div>
        </td>
        <td><span class="badge badge-${categoryColor(q.category)}">${q.category}</span></td>
        <td>
          <div style="display:flex;align-items:center;gap:6px">
            <div style="width:8px;height:8px;border-radius:50%;background:${q.response_time_ms < 1000 ? 'var(--success)' : 'var(--warning)'}"></div>
            <span style="font-family:var(--font-mono);font-size:12px">${q.response_time_ms}ms</span>
          </div>
        </td>
        <td style="font-size:13px;color:var(--text-tertiary)">${timeAgo(q.timestamp)}</td>
      </tr>`).join('')}</tbody></table></div></div>`;
  } catch (err) {
    el.innerHTML = `<div class="empty-state"><h3 class="text-error">Error loading history</h3><p>${err.message}</p></div>`;
  }
}

// ── Organization ────────────────────────────────────────────
async function loadOrg() {
  const el = document.getElementById('orgCard');
  el.innerHTML = '<div style="padding:40px"><div class="skeleton" style="height:200px"></div></div>';
  try {
    const org = await API.getOrganization();
    const user = API.getUser();
    
    el.innerHTML = `<div style="padding:32px;display:flex;flex-direction:column;gap:32px">
      <div style="display:flex;align-items:flex-start;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:16px">
          <div style="width:64px;height:64px;background:linear-gradient(135deg,var(--accent) 0%,#1e40af 100%);border-radius:16px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;font-weight:700;box-shadow:0 4px 12px rgba(37,99,235,0.2)">
            ${(org.name || 'O')[0].toUpperCase()}
          </div>
          <div>
            <div style="font-size:24px;font-weight:700;letter-spacing:-0.02em">${escapeHtml(org.name)}</div>
            <div style="font-size:14px;color:var(--text-tertiary);margin-top:2px">Workspace ID: <code style="background:var(--bg-tertiary);padding:2px 6px;border-radius:4px;font-family:var(--font-mono);color:var(--text-secondary)">${org.slug}</code></div>
          </div>
        </div>
      </div>
      
      <div style="height:1px;background:var(--border-primary)"></div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px">
        <div style="background:var(--bg-secondary);padding:20px;border-radius:12px;border:1px solid var(--border-primary)">
          <div style="font-size:12px;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-tertiary);font-weight:600;margin-bottom:8px">Documents Indexed</div>
          <div style="font-size:28px;font-weight:700">${org.document_count||0}</div>
        </div>
        <div style="background:var(--bg-secondary);padding:20px;border-radius:12px;border:1px solid var(--border-primary)">
          <div style="font-size:12px;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-tertiary);font-weight:600;margin-bottom:8px">Your Role</div>
          <div style="font-size:20px;font-weight:600;color:var(--text-primary);display:flex;align-items:center;gap:8px">
            <span class="status-dot online"></span>
            ${user.is_admin?'Workspace Admin':'Member'}
          </div>
        </div>
        <div style="background:var(--bg-secondary);padding:20px;border-radius:12px;border:1px solid var(--border-primary)">
          <div style="font-size:12px;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-tertiary);font-weight:600;margin-bottom:8px">Created</div>
          <div style="font-size:16px;font-weight:500;margin-top:4px">${org.created_at ? new Date(org.created_at).toLocaleDateString(undefined, {month:'long', day:'numeric', year:'numeric'}) : '—'}</div>
        </div>
      </div>
      
      ${org.description ? `
      <div>
        <div style="font-size:14px;font-weight:600;margin-bottom:8px">About Organization</div>
        <div style="font-size:15px;line-height:1.6;color:var(--text-secondary);background:var(--bg-secondary);padding:16px;border-radius:8px">${escapeHtml(org.description)}</div>
      </div>` : ''}
    </div>`;
  } catch (err) {
    el.innerHTML = `<div style="padding:32px"><p class="text-error" style="font-weight:500">Could not load organization details.</p></div>`;
  }
}

async function loadTeam() {
  try {
    const user = API.getUser();
    
    // Toggle Admin Button
    const addBtn = document.getElementById('addMemberBtn');
    if (addBtn) {
      addBtn.style.display = user.is_admin ? 'inline-flex' : 'none';
    }
    
    // Load the workspace team members
    await loadOrgUsers();
  } catch (err) {
    const listEl = document.getElementById('orgMembersList');
    if (listEl) {
      listEl.innerHTML = `<div style="padding:32px;text-align:center;color:var(--error);font-size:12px;">Failed to initialize team page: ${err.message}</div>`;
    }
  }
}

// ── Admin / Settings ────────────────────────────────────────
function switchAdminTab(tab) {
  document.querySelectorAll('#adminTabs .tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  renderAdminTab(tab);
}

function renderAdminTab(tab) {
  const el = document.getElementById('adminContent');
  const user = API.getUser();

  if (tab === 'general') {
    el.innerHTML = `<div class="card" style="max-width:640px;box-shadow:0 4px 12px rgba(0,0,0,0.02)">
      <div style="padding:24px;border-bottom:1px solid var(--border-primary)">
        <h3 style="font-size:16px;font-weight:600">Personal Information</h3>
        <p style="font-size:13px;color:var(--text-secondary);margin-top:4px">Update your personal profile details.</p>
      </div>
      <div style="padding:24px;display:flex;flex-direction:column;gap:20px">
        <div class="input-group">
          <label style="font-size:13px">Full Name</label>
          <input id="profileName" class="input" value="${escapeHtml(user.full_name||'')}">
        </div>
        <div class="input-group">
          <label style="font-size:13px">Email Address</label>
          <input id="profileEmail" class="input" type="email" value="${escapeHtml(user.email||'')}">
        </div>
        <div class="input-group">
          <label style="font-size:13px">Role</label>
          <input class="input" value="${user.is_admin?'Administrator':'Member'}" readonly style="background:var(--bg-secondary);color:var(--text-secondary)">
        </div>
      </div>
      <div style="padding:16px 24px;background:var(--bg-secondary);border-top:1px solid var(--border-primary);display:flex;justify-content:flex-end">
        <button class="btn btn-primary" onclick="saveProfileSettings(this)">Save Changes</button>
      </div>
    </div>`;
  } else if (tab === 'audit') {

    el.innerHTML = `<div class="card" style="max-width:640px;box-shadow:0 4px 12px rgba(0,0,0,0.02)">
      <div style="padding:24px;border-bottom:1px solid var(--border-primary)">
        <h3 style="font-size:16px;font-weight:600">Security Audit Log</h3>
        <p style="font-size:13px;color:var(--text-secondary);margin-top:4px">Track security events in your workspace.</p>
      </div>
      <div style="padding:16px 24px">
        <div class="timeline">
          <div class="timeline-item">
            <div class="timeline-dot"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg></div>
            <div class="timeline-content">
              <div class="timeline-text">User authenticated successfully</div>
              <div class="timeline-time" style="display:flex;align-items:center;gap:8px">
                <span>${new Date().toLocaleString()}</span>
                <span style="font-family:var(--font-mono);background:var(--bg-secondary);padding:2px 4px;border-radius:4px">IP: 192.168.1.1</span>
              </div>
            </div>
          </div>
          <div class="timeline-item">
            <div class="timeline-dot"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>
            <div class="timeline-content">
              <div class="timeline-text">Session started</div>
              <div class="timeline-time">${new Date().toLocaleString()}</div>
            </div>
          </div>
        </div>
      </div>
    </div>`;
  }
}

// ── Workspace Team Management ───────────────────────────────
async function loadOrgUsers() {
  const listEl = document.getElementById('orgMembersList');
  if (!listEl) return;
  listEl.innerHTML = '<div style="padding:32px;text-align:center"><div class="spinner" style="margin:0 auto"></div></div>';
  
  try {
    const users = await API.listOrgUsers();
    if (!users || !users.length) {
      listEl.innerHTML = '<div style="padding:32px;text-align:center;font-size:12px;color:var(--text-tertiary)">No workspace members found.</div>';
      return;
    }
    
    listEl.innerHTML = `
      <div class="table-wrap" style="border:none;border-radius:0;">
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Joined Date</th>
            </tr>
          </thead>
          <tbody>
            ${users.map(u => `
              <tr>
                <td style="font-weight:600;color:var(--text-primary);display:flex;align-items:center;gap:10px;">
                  <div style="width:28px;height:28px;background:var(--bg-tertiary);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:var(--text-secondary)">
                    ${escapeHtml(u.full_name || 'U')[0].toUpperCase()}
                  </div>
                  ${escapeHtml(u.full_name)}
                </td>
                <td style="color:var(--text-secondary)">${escapeHtml(u.email)}</td>
                <td>
                  <span class="badge ${u.is_admin ? 'badge-blue' : 'badge-default'}">
                    ${u.is_admin ? 'Admin' : 'Member'}
                  </span>
                </td>
                <td style="color:var(--text-tertiary)">${new Date(u.created_at).toLocaleDateString(undefined, {month:'short', day:'numeric', year:'numeric'})}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div></div>`;
  } catch (err) {
    listEl.innerHTML = `<div style="padding:32px;text-align:center;color:var(--error);font-size:12px;">Failed to load team members: ${err.message}</div>`;
  }
}

function openAddUserModal() {
  const modal = document.getElementById('addUserModal');
  if (modal) modal.classList.remove('hidden');
  
  // Clear inputs and error
  document.getElementById('newUserName').value = '';
  document.getElementById('newUserEmail').value = '';
  document.getElementById('newUserPassword').value = '';
  document.getElementById('newUserAdmin').checked = false;
  
  const errEl = document.getElementById('addUserError');
  if (errEl) errEl.classList.add('hidden');
}

function closeAddUserModal(event) {
  if (event && event.stopPropagation) event.stopPropagation();
  const modal = document.getElementById('addUserModal');
  if (modal) modal.classList.add('hidden');
}


async function handleAddUserSubmit(event) {
  event.preventDefault();
  
  const btn = document.getElementById('addUserBtn');
  const errEl = document.getElementById('addUserError');
  if (errEl) errEl.classList.add('hidden');
  
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;border-top-color:#fff;margin:0 auto"></div>';
  }
  
  const name = document.getElementById('newUserName').value;
  const email = document.getElementById('newUserEmail').value;
  const password = document.getElementById('newUserPassword').value;
  const isAdmin = document.getElementById('newUserAdmin').checked;
  
  try {
    await API.createOrgUser(email, password, name, isAdmin);
    showToast("Workspace member added successfully", "success");
    closeAddUserModal();
    await loadOrgUsers();
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || "Failed to add member. Please try again.";
      errEl.classList.remove('hidden');
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = 'Create Account';
    }
  }
}
