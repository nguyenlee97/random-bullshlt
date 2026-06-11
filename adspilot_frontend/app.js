/**
 * app.js — Navigation, state management, utilities
 * Entry point: initializes the app after DOM is ready
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

/* ── Navigation ─────────────────────────────────────────────────────────────── */

function navTo(v, payload) {
  // Reset form state when navigating away from create (unless going to create)
  if (currentView === 'create' && v !== 'create') {
    editing   = null;
    formState = null;
  }
  currentView = v;

  // Update sidebar active state
  document.querySelectorAll('.sidebar li').forEach(li => {
    li.classList.toggle('active', li.dataset.nav === v);
  });
  // Update topbar nav active state
  document.querySelectorAll('#topNav button').forEach(b => {
    b.classList.toggle('on', b.dataset.view === v);
  });

  if      (v === 'orders')                        renderOrders();
  else if (v === 'create')                        renderCreate(payload);
  else if (v === 'report')                        renderReport();
  else if (v === 'api')                           renderApiConsole();
  else if (v === 'docs')                          renderDocs();
  else if (v === 'log')                           renderApiConsole();
  else if (v === 'conversion' || v === 'bundle')  renderPlaceholder(v);
}

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
    // backend returns { count, items } or might return array
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
  // Verify backend connectivity once on load
  Api.healthCheck()
    .then(() => { /* backend OK */ })
    .catch(() => {
      toast('⚠ Backend offline — check localhost:3000', true);
    });

  navTo('orders');
});
