/* ═══ Public user — organization search, dropdown & subscriptions ═══ */

let browseOrgsCache = [];
let pendingSubscriptionIds = [];
let subSearchDebounce = null;

function getOrgById(orgId) {
  return browseOrgsCache.find((o) => o.organization_id === orgId);
}

function isSubOnboarding() {
  return (
    window.location.hash === '#subscriptions' ||
    window.location.search.includes('onboarding=1') ||
    API.getSubscribedOrgIds().length === 0
  );
}

function renderSubscriptionsShell() {
  const panel = document.getElementById('subscriptionsPanel');
  if (!panel) return;

  const onboarding = isSubOnboarding();
  panel.innerHTML = `
    ${onboarding ? `
    <div class="sub-onboarding">
      <h2>Welcome — find your organization</h2>
      <p>Search or pick your organization from the dropdown. You can query only <strong>public</strong> documents from organizations you add.</p>
    </div>` : `
    <div class="page-header" style="padding:0;margin-bottom:20px">
      <div>
        <h1 class="page-title">Your organizations</h1>
        <p class="page-desc">Manage which organizations you can search.</p>
      </div>
    </div>`}

    <div class="sub-toolbar">
      <div class="sub-search-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="search" id="orgSearchInput" class="input" placeholder="Search organizations by name…" autocomplete="off"
          oninput="onOrgSearchInput(this.value)" aria-label="Search organizations">
      </div>
      <div class="sub-quick-select">
        <label for="orgQuickSelect">Quick select from list</label>
        <select id="orgQuickSelect" class="input" onchange="onOrgQuickSelect(this)">
          <option value="">Choose an organization…</option>
        </select>
      </div>
    </div>

    <div class="sub-chips-section">
      <div class="sub-chips-label">Selected (<span id="subSelectedCount">0</span>)</div>
      <div class="sub-chips" id="subSelectedChips">
        <span style="font-size:13px;color:var(--text-tertiary)">No organization selected yet</span>
      </div>
    </div>

    <div class="sub-results-meta">
      <span id="subResultsCount">Loading…</span>
      <button type="button" class="btn btn-ghost btn-sm" onclick="clearOrgSearch()">Clear search</button>
    </div>
    <div class="sub-org-grid" id="subOrgResults"></div>

    <div class="sub-footer-bar">
      <span id="subFooterHint" style="font-size:13px;color:var(--text-secondary)">Select at least one organization to continue</span>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${onboarding ? '' : '<button type="button" class="btn btn-secondary" onclick="navigate(\'chat\')">Ask AI</button>'}
        <button type="button" class="btn btn-primary" id="saveSubscriptionsBtn" onclick="saveSubscriptions()" disabled>
          Save &amp; continue
        </button>
      </div>
    </div>`;

  populateOrgQuickSelect(browseOrgsCache);
  renderSelectedChips();
  renderOrgResultCards(browseOrgsCache);
}

async function loadSubscriptions() {
  const panel = document.getElementById('subscriptionsPanel');
  if (!panel) return;

  panel.innerHTML = '<div style="padding:48px;text-align:center"><div class="spinner" style="margin:0 auto"></div></div>';

  try {
    browseOrgsCache = await API.browseOrganizations();
    pendingSubscriptionIds = [...API.getSubscribedOrgIds()];
    renderSubscriptionsShell();
    syncPublicQueryOrgBar();
  } catch (err) {
    panel.innerHTML = `<div style="padding:32px;color:var(--error)">Failed to load organizations: ${escapeHtml(err.message)}</div>`;
  }
}

function populateOrgQuickSelect(orgs) {
  const sel = document.getElementById('orgQuickSelect');
  if (!sel) return;
  const sorted = [...orgs].sort((a, b) => a.name.localeCompare(b.name));
  sel.innerHTML =
    '<option value="">Choose an organization…</option>' +
    sorted
      .map(
        (o) =>
          `<option value="${escapeHtml(o.organization_id)}">${escapeHtml(o.name)}</option>`
      )
      .join('');
}

function onOrgQuickSelect(selectEl) {
  const orgId = selectEl.value;
  if (!orgId) return;
  toggleSubscriptionOrg(orgId, true);
  selectEl.value = '';
  showToast(`Added ${getOrgById(orgId)?.name || 'organization'}`, 'success');
}

function onOrgSearchInput(value) {
  clearTimeout(subSearchDebounce);
  subSearchDebounce = setTimeout(() => fetchAndRenderOrgSearch(value), 280);
}

function clearOrgSearch() {
  const input = document.getElementById('orgSearchInput');
  if (input) input.value = '';
  fetchAndRenderOrgSearch('');
}

async function fetchAndRenderOrgSearch(query) {
  const grid = document.getElementById('subOrgResults');
  const countEl = document.getElementById('subResultsCount');
  if (!grid) return;

  grid.innerHTML = '<div style="grid-column:1/-1;padding:24px;text-align:center"><div class="spinner" style="margin:0 auto"></div></div>';
  if (countEl) countEl.textContent = 'Searching…';

  try {
    const results = await API.browseOrganizations(query);
    if (!query.trim()) {
      browseOrgsCache = results;
    } else {
      const merged = new Map(browseOrgsCache.map((o) => [o.organization_id, o]));
      results.forEach((o) => merged.set(o.organization_id, o));
      browseOrgsCache = [...merged.values()].sort((a, b) => a.name.localeCompare(b.name));
    }
    populateOrgQuickSelect(browseOrgsCache);
    renderOrgResultCards(results);
  } catch (err) {
    grid.innerHTML = `<div class="sub-empty-results">Search failed: ${escapeHtml(err.message)}</div>`;
    if (countEl) countEl.textContent = '';
  }
}

function renderOrgResultCards(orgs) {
  const grid = document.getElementById('subOrgResults');
  const countEl = document.getElementById('subResultsCount');
  if (!grid) return;

  if (!orgs.length) {
    grid.innerHTML = `
      <div class="sub-empty-results" style="grid-column:1/-1">
        <p style="margin:0 0 8px;font-weight:600">No organizations found</p>
        <p style="margin:0;font-size:13px">Try another name, or ask your organization to create a workspace.</p>
      </div>`;
    if (countEl) countEl.textContent = '0 results';
    return;
  }

  if (countEl) {
    countEl.textContent = `${orgs.length} Organzations found`;
  }

  grid.innerHTML = orgs
    .map((o) => {
      const selected = pendingSubscriptionIds.includes(o.organization_id);
      const safeId = escapeHtml(o.organization_id);
      return `
        <button type="button" class="sub-org-card${selected ? ' selected' : ''}"
          data-org-id="${safeId}" onclick="toggleSubscriptionOrg('${safeId}', ${selected ? 'false' : 'true'})"
          aria-pressed="${selected}">
          <div class="sub-org-check">${selected ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>' : ''}</div>
          <div class="sub-org-card-body">
            <strong>${escapeHtml(o.name)}</strong>
            <span>${escapeHtml(o.slug || 'workspace')}</span>
            ${o.description ? `<p>${escapeHtml(o.description)}</p>` : ''}
          </div>
        </button>`;
    })
    .join('');
}

function renderSelectedChips() {
  const wrap = document.getElementById('subSelectedChips');
  const countEl = document.getElementById('subSelectedCount');
  const saveBtn = document.getElementById('saveSubscriptionsBtn');
  const hint = document.getElementById('subFooterHint');

  if (countEl) countEl.textContent = String(pendingSubscriptionIds.length);
  if (saveBtn) saveBtn.disabled = pendingSubscriptionIds.length === 0;
  if (hint) {
    hint.textContent = pendingSubscriptionIds.length
      ? `${pendingSubscriptionIds.length} organization${pendingSubscriptionIds.length === 1 ? '' : 's'} ready to save`
      : 'Select at least one organization to continue';
  }

  if (!wrap) return;

  if (!pendingSubscriptionIds.length) {
    wrap.innerHTML = '<span style="font-size:13px;color:var(--text-tertiary)">Use search or the dropdown above to add organizations</span>';
    return;
  }

  wrap.innerHTML = pendingSubscriptionIds
    .map((id) => {
      const name = getOrgById(id)?.name || id;
      return `
        <span class="sub-chip">
          ${escapeHtml(name)}
          <button type="button" title="Remove" onclick="toggleSubscriptionOrg('${escapeHtml(id)}', false); event.stopPropagation();">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </span>`;
    })
    .join('');
}

function toggleSubscriptionOrg(orgId, checked) {
  if (checked) {
    if (!pendingSubscriptionIds.includes(orgId)) pendingSubscriptionIds.push(orgId);
  } else {
    pendingSubscriptionIds = pendingSubscriptionIds.filter((id) => id !== orgId);
  }
  renderSelectedChips();
  const searchVal = document.getElementById('orgSearchInput')?.value || '';
  const q = searchVal.trim().toLowerCase();
  const visible = q
    ? browseOrgsCache.filter((o) =>
        [o.name, o.slug, o.description || ''].join(' ').toLowerCase().includes(q)
      )
    : browseOrgsCache;
  renderOrgResultCards(visible.length ? visible : browseOrgsCache);
}

function getActiveQueryOrgIds() {
  if (!API.isPublicUser()) return null;
  const sel = document.getElementById('publicQueryOrgSelect');
  if (sel) {
    if (sel.value) return [sel.value];
    return API.getSubscribedOrgIds();
  }
  const bar = document.getElementById('publicQueryOrgBarChecks');
  if (!bar) return API.getSubscribedOrgIds();
  const checked = [...bar.querySelectorAll('input[type=checkbox]:checked')].map((el) => el.value);
  return checked.length ? checked : API.getSubscribedOrgIds();
}

async function syncPublicQueryOrgBar() {
  const bar = document.getElementById('publicQueryOrgBar');
  const checks = document.getElementById('publicQueryOrgBarChecks');
  if (!bar || !checks || !API.isPublicUser()) return;

  if (!browseOrgsCache.length) {
    try {
      browseOrgsCache = await API.browseOrganizations();
    } catch (_) { /* ignore */ }
  }

  bar.classList.remove('hidden');
  bar.style.display = 'flex';
  const subscribed = API.getSubscribedOrgIds();
  const orgMap = Object.fromEntries(browseOrgsCache.map((o) => [o.organization_id, o.name]));

  if (!subscribed.length) {
    checks.innerHTML =
      '<span style="font-size:12px;color:var(--text-tertiary)">' +
      '<a href="#" onclick="navigate(\'subscriptions\');return false" style="color:var(--accent)">Add organizations</a> to start searching</span>';
    return;
  }

  const options = subscribed
    .map(
      (id) =>
        `<option value="${escapeHtml(id)}">${escapeHtml(orgMap[id] || id)}</option>`
    )
    .join('');

  checks.innerHTML = `
    <label style="font-size:12px;color:var(--text-secondary);white-space:nowrap">Organization:</label>
    <select id="publicQueryOrgSelect" class="input" style="min-width:200px;padding:8px 12px;font-size:13px" onchange="onPublicQueryOrgChange()">
      ${subscribed.length > 1 ? '<option value="">All subscribed</option>' : ''}
      ${options}
    </select>
    ${subscribed.length > 1 ? `
    <span style="font-size:11px;color:var(--text-tertiary)">or filter:</span>
    ${subscribed
      .map(
        (id) => `
      <label style="display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer">
        <input type="checkbox" value="${escapeHtml(id)}" checked onchange="onPublicQueryOrgChange()">
        ${escapeHtml(orgMap[id] || id)}
      </label>`
      )
      .join('')}` : ''}`;
}

function onPublicQueryOrgChange() {
  const ids = getActiveQueryOrgIds();
  if (API.isPublicUser() && (!ids || !ids.length)) {
    showToast('Select an organization to search', 'error');
  }
}

async function saveSubscriptions() {
  const btn = document.getElementById('saveSubscriptionsBtn');
  if (!pendingSubscriptionIds.length) {
    showToast('Select at least one organization', 'error');
    return;
  }
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Saving…';
  }
  try {
    const user = await API.subscribeToOrganizations(pendingSubscriptionIds);
    API.setUser(user);
    updateSidebarForRole();
    loadOrgName();
    syncPublicQueryOrgBar();
    showToast('Organizations saved — you can now use Ask AI', 'success');
    // Clear URL hashes and search parameters so onboarding is complete, then navigate to Ask AI tab
    window.location.hash = '';
    window.history.replaceState(null, '', window.location.pathname);
    navigate('chat');
  } catch (err) {
    showToast(err.message || 'Failed to save', 'error');
  } finally {
    if (btn) {
      btn.disabled = pendingSubscriptionIds.length === 0;
      btn.textContent = 'Save & continue';
    }
  }
}
