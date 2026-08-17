/**
 * app.js — Navigation, state management, utilities
 * Routing: hash-based (#/orders, #/create, #/edit/ORD-001, #/edit/ORD-001/creatives)
 */

/* ── State ──────────────────────────────────────────────────────────────────── */
let currentView = 'orders';
let editing     = null;    // orderId being edited
let formState   = null;    // working copy of form data
let zonesCache  = null;    // cached zone catalog {groups, channels, placements}
let targetingCache = null; // cached targeting options
let dmpCache    = null;    // cached DMP items array

/* ── Utility functions ──────────────────────────────────────────────────────── */

function toast(tx, isError = false) {
  const t  = document.getElementById('toast');
  const tx2 = document.getElementById('toastTx');
  tx2.textContent = tx;
  t.classList.toggle('error', isError);
  t.classList.add('show');
  clearTimeout(window._tt);
  window._tt = setTimeout(() => t.classList.remove('show'), 2200);
}

function fmt(n) {
  if (!n) return '0';
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(2).replace(/\.?0+$/, '') + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
  return String(n);
}

function fmtVND(n) {
  return (n || 0).toLocaleString('vi-VN');
}

function escHTML(s) {
  return (s == null ? '' : String(s))
    .replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function setMain(html) {
  document.getElementById('main').innerHTML = html;
}

function showLoading() {
  setMain(`<div class="loading-state"><div class="spinner"></div><p>Loading...</p></div>`);
}

/* ── In-page Confirm Modal (replaces browser confirm()) ─────────────────────── */

/**
 * Show a themed in-page confirmation dialog.
 * @param {string}   message  - The question to show the user
 * @param {Function} onOk     - Called when user clicks the confirm button
 * @param {string}   [okLabel='Delete'] - Label for the confirm button
 */
function showConfirm(message, onOk, okLabel = 'Delete') {
  const overlay  = document.getElementById('confirmOverlay');
  const msgEl    = document.getElementById('confirmMsg');
  const okBtn    = document.getElementById('confirmOk');
  const cancelBtn = document.getElementById('confirmCancel');

  msgEl.textContent = message;
  okBtn.textContent = okLabel;
  overlay.classList.remove('hidden');

  // Clone buttons to clear old listeners
  const newOk     = okBtn.cloneNode(true);
  const newCancel = cancelBtn.cloneNode(true);
  okBtn.replaceWith(newOk);
  cancelBtn.replaceWith(newCancel);

  function close() { overlay.classList.add('hidden'); }

  newOk.addEventListener('click', () => { close(); onOk(); });
  newCancel.addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); }, { once: true });
}

/* ── URL Hash Router ────────────────────────────────────────────────────────── */

/**
 * Route map:
 *   #/orders                  → Orders list
 *   #/create                  → New campaign form
 *   #/create/zones            → New campaign form, scroll to Zones section
 *   #/create/targeting        → scroll to Targeting
 *   #/create/dmp              → scroll to DMP
 *   #/create/creatives        → scroll to Creatives
 *   #/edit/ORD-001            → Edit campaign ORD-001
 *   #/edit/ORD-001/creatives  → Edit ORD-001, scroll to Creatives
 *   #/report                  → Report view
 *   #/api                     → Read-only API activity log
 */
function parseHash() {
  const hash = window.location.hash.replace(/^#\/?/, ''); // strip leading #/
  const parts = hash.split('/').filter(Boolean);
  // parts[0] = view, parts[1] = id or section, parts[2] = section
  const view    = parts[0] || 'orders';
  const second  = parts[1] || null;
  const third   = parts[2] || null;

  const SECTIONS = ['info', 'zones', 'targeting', 'dmp', 'creatives'];

  if (view === 'edit' && second && !SECTIONS.includes(second)) {
    // #/edit/ORD-001  or  #/edit/ORD-001/creatives
    return { view: 'create', orderId: second, section: third };
  }
  if (view === 'create') {
    return { view: 'create', orderId: null, section: second };
  }
  return { view, orderId: null, section: second };
}

/** Update the URL hash without triggering hashchange listener */
function setHash(hash, { replace = false } = {}) {
  if (replace) {
    history.replaceState(null, '', hash);
  } else {
    history.pushState(null, '', hash);
  }
}

/* ── Navigation ─────────────────────────────────────────────────────────────── */

/**
 * Navigate to a view, optionally scrolling to a named section.
 * Updates the URL hash for deep-linking.
 * @param {string} v        - view name: 'orders'|'create'|'report'|'api'
 * @param {*}      payload  - extra data passed to render fn (unused currently)
 * @param {string} section  - optional section ID to scroll to after render
 */
function navTo(v, payload, section) {
  // Reset form state when navigating away from create
  if (currentView === 'create' && v !== 'create') {
    editing   = null;
    formState = null;
  }
  currentView = v;

  // ── Update URL hash ──
  if (v === 'create' && editing) {
    const sec = section ? `/${section}` : '';
    setHash(`#/edit/${editing}${sec}`);
  } else if (v === 'create') {
    const sec = section ? `/${section}` : '';
    setHash(`#/create${sec}`);
  } else {
    setHash(`#/${v}`);
  }

  // ── Update sidebar & topbar active state ──
  document.querySelectorAll('.sidebar li').forEach(li => {
    li.classList.toggle('active', li.dataset.nav === v);
  });
  document.querySelectorAll('#topNav button').forEach(b => {
    b.classList.toggle('on', b.dataset.view === v);
  });

  // ── Render ──
  if      (v === 'orders')                        renderOrders();
  else if (v === 'create')                        renderCreate(payload, section);
  else if (v === 'report')                        renderReport();
  else if (v === 'api')                           renderApiConsole();
  else if (v === 'log')                           renderApiConsole();
  else if (v === 'conversion' || v === 'bundle')  renderPlaceholder(v);
  else                                             navTo('orders');
}

/**
 * Scroll the main panel to a named section inside the create/edit form.
 * Section IDs: 'section-info', 'section-zones', 'section-targeting',
 *              'section-dmp', 'section-creatives'
 * Also updates the URL hash.
 */
function scrollToSection(section) {
  const el = document.getElementById('section-' + section);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  // Update hash with section
  if (editing) {
    setHash(`#/edit/${editing}/${section}`);
  } else {
    setHash(`#/create/${section}`);
  }
  // Update tab bar highlight
  document.querySelectorAll('.form-tab').forEach(t => {
    t.classList.toggle('on', t.dataset.section === section);
  });
}

/* ── hashchange listener (browser back/forward, direct URL entry) ────────────── */

function routeFromHash() {
  const { view, orderId, section } = parseHash();
  if (view === 'create' && orderId) {
    // Deep link to edit: load order then render
    editOrder(orderId).then(() => {
      if (section) setTimeout(() => scrollToSection(section), 400);
    }).catch(() => navTo('orders', null, null));
  } else {
    navTo(view, null, section || null);
    if (section && (view === 'create')) {
      setTimeout(() => scrollToSection(section), 400);
    }
  }
}

window.addEventListener('popstate', routeFromHash);

/* ── Sidebar listeners ──────────────────────────────────────────────────────── */
document.querySelectorAll('.sidebar li').forEach(li => {
  li.addEventListener('click', () => navTo(li.dataset.nav));
});

/* ── Sidebar search filter ───────────────────────────────────────────────────── */
document.getElementById('sidebarSearch').addEventListener('input', function () {
  const q = this.value.toLowerCase();
  document.querySelectorAll('.sidebar li').forEach(li => {
    const text = li.textContent.toLowerCase();
    li.style.display = text.includes(q) ? '' : 'none';
  });
});

/* ── Zone / Targeting Cache Loaders ────────────────────────────────────────── */

async function loadZones() {
  if (zonesCache) return zonesCache;
  try {
    zonesCache = await Api.listZones();
    return zonesCache;
  } catch (e) {
    return { groups: [], channels: {}, placements: [] };
  }
}

async function loadTargeting() {
  if (targetingCache) return targetingCache;
  try {
    targetingCache = await Api.listTargetingOptions();
    return targetingCache;
  } catch (e) {
    return {};
  }
}

async function loadDmp() {
  if (dmpCache) return dmpCache;
  try {
    const resp = await Api.listDmpAttributes({ limit: 400 });
    dmpCache = Array.isArray(resp) ? resp : (resp.items || []);
    return dmpCache;
  } catch (e) {
    return [];
  }
}

/* ── Placeholder for stub views ──────────────────────────────────────────────── */
function renderPlaceholder(v) {
  const labels = {
    conversion: 'Conversion Tracking',
    bundle:     'Ads Bundle',
    log:        'System Log',
  };
  const label = labels[v] || v;
  setMain(`
    <div class="crumb"><b>${escHTML(label)}</b></div>
    <div class="card">
      <div class="body placeholder">
        <div class="ph-icon">🚧</div>
        <h3>${escHTML(label)}</h3>
        <p>This section is not yet implemented in this demo.<br>
           Focus areas: <a onclick="navTo('orders')">Orders</a>,
           <a onclick="navTo('create')">Create</a>,
           <a onclick="navTo('api')">API Console</a>.</p>
      </div>
    </div>`);
}

/* ── Boot ────────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  Api.healthCheck()
    .then(() => { /* backend OK */ })
    .catch(() => {
      toast('⚠ Backend offline — check API', true);
    });

  // Route from hash if present, else default to orders
  const hash = window.location.hash;
  if (hash && hash !== '#/' && hash !== '#/orders') {
    routeFromHash();
  } else {
    navTo('orders');
  }
});
