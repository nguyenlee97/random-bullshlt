/**
 * app.js — Tab router, filter state, data loading
 * Imports api.js functions, delegates rendering to tab modules.
 */
import { fetchData, fetchSummary, fetchByDate, fetchByCampaign, fetchByPlacement, fetchHealth } from './api.js';
import { render as renderDailyOps }      from './tabs/daily-ops.js';
import { render as renderAwareness }     from './tabs/awareness.js';
import { render as renderConsideration } from './tabs/consideration.js';
import { render as renderConversion }    from './tabs/conversion.js';
import { render as renderRetention }     from './tabs/retention.js';
import { render as renderExecutive }     from './tabs/executive.js';

/* ── Shared state ───────────────────────────────────────────────── */
const State = {
  allData: [],       // raw analytics records from backend
  filtered: [],      // after client-side filter applied
  summary: null,     // /api/analytics/summary response
  byDate: [],        // /api/analytics/by-date response
  byCampaign: [],    // /api/analytics/by-campaign response
  byPlacement: [],   // /api/analytics/by-placement response
  filters: {
    brand: '',
    zone: '',
    audience: '',
    startDate: '',
    endDate: ''
  },
  activeTab: 'op',
  loading: false
};

/* ── Chart registry (destroy before re-render) ──────────────────── */
export const Charts = {};

export function destroyChart(id) {
  if (Charts[id]) {
    Charts[id].destroy();
    delete Charts[id];
  }
}

export function registerChart(id, instance) {
  destroyChart(id);
  Charts[id] = instance;
}

/* ── DOM refs ───────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);

const els = {
  loadingOverlay: $('loadingOverlay'),
  errorState:     $('errorState'),
  errorMsg:       $('errorMsg'),
  totalRows:      $('totalRows'),
  totalSpend:     $('totalSpend'),
  filteredCount:  $('filteredCount'),
  connDot:        $('connDot'),
  connLabel:      $('connLabel'),
  fBrand:         $('fBrand'),
  fZone:          $('fZone'),
  fAudience:      $('fAudience'),
  fStart:         $('fStart'),
  fEnd:           $('fEnd'),
  btnApply:       $('btnApplyFilter'),
  btnReset:       $('btnResetFilter'),
  btnRetry:       $('btnRetry'),
  tabs:           $('tabs'),
};

/* ── Formatters ─────────────────────────────────────────────────── */
export function fmt(n, decimals = 0) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Number(n).toLocaleString('vi-VN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

export function fmtPct(n, decimals = 1) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return (n * 100).toFixed(decimals) + '%';
}

export function fmtVND(n) {
  if (!n) return '₫0';
  if (n >= 1_000_000_000) return '₫' + (n / 1_000_000_000).toFixed(1) + 'B';
  if (n >= 1_000_000)     return '₫' + (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)         return '₫' + (n / 1_000).toFixed(0) + 'K';
  return '₫' + n;
}

export function fmtK(n) {
  if (!n) return '0';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

/* ── Color palette ──────────────────────────────────────────────── */
export const COLORS = [
  '#1f3551', '#2c7fb8', '#5ba33d', '#c98a14', '#6e4cb8',
  '#0d8a8a', '#c54a8a', '#c0392b', '#2980b9', '#27ae60'
];

export function alpha(hex, a) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}

/* ── Connection check ───────────────────────────────────────────── */
async function checkConnection() {
  try {
    await fetchHealth();
    els.connDot.className = 'conn-dot ok';
    els.connLabel.textContent = 'Connected · :3000';
  } catch {
    els.connDot.className = 'conn-dot err';
    els.connLabel.textContent = 'Offline';
  }
}

/* ── Data loading ───────────────────────────────────────────────── */
async function loadAll() {
  State.loading = true;
  els.loadingOverlay.classList.remove('hidden');
  els.errorState.classList.add('hidden');

  try {
    const [dataRes, summaryRes, byDateRes, byCampRes, byPlacementRes] = await Promise.all([
      fetchData({ limit: 2000 }),
      fetchSummary(),
      fetchByDate(),
      fetchByCampaign(),
      fetchByPlacement()
    ]);

    // Normalize — backend may return { data: [...] } or just [...]
    State.allData      = Array.isArray(dataRes) ? dataRes : (dataRes.data || []);
    State.summary      = summaryRes;
    State.byDate       = Array.isArray(byDateRes) ? byDateRes : (byDateRes.data || []);
    State.byCampaign   = Array.isArray(byCampRes) ? byCampRes : (byCampRes.data || []);
    State.byPlacement  = Array.isArray(byPlacementRes) ? byPlacementRes : (byPlacementRes.data || []);

    populateFilterDropdowns();
    applyClientFilter();
    updateTopbarStats();
    renderActiveTab();

    els.loadingOverlay.classList.add('hidden');
  } catch (err) {
    console.error('[analytics] Load failed:', err);
    els.loadingOverlay.classList.add('hidden');
    els.errorMsg.textContent = err.message || 'Backend at localhost:3000 is unreachable.';
    els.errorState.classList.remove('hidden');
  } finally {
    State.loading = false;
  }
}

/* ── Filter dropdowns ───────────────────────────────────────────── */
function populateFilterDropdowns() {
  const data = State.allData;

  // Real backend: campaignId, placementId, channel
  // Mock data: brand, zone, audienceSegment
  const brands = [...new Set(data.map(r =>
    r.brand || r.Brand || (r.campaignId || '').replace(/-\d+$/, '') || ''
  ).filter(Boolean))].sort();

  const zones = [...new Set(data.map(r =>
    r.placementId || r.zone || r.Zone || ''
  ).filter(Boolean))].sort();

  const audiences = [...new Set(data.map(r =>
    r.audienceSegment || r['Audience Segment'] || r.channel || ''
  ).filter(Boolean))].sort();

  fillSelect(els.fBrand,    brands,    'All campaigns');
  fillSelect(els.fZone,     zones,     'All placements');
  fillSelect(els.fAudience, audiences, 'All channels');
}


function fillSelect(sel, options, placeholder) {
  const cur = sel.value;
  sel.innerHTML = `<option value="">${placeholder}</option>`;
  options.forEach(v => {
    const o = document.createElement('option');
    o.value = v;
    o.textContent = v;
    if (v === cur) o.selected = true;
    sel.appendChild(o);
  });
}

/* ── Client-side filter ─────────────────────────────────────────── */
function applyClientFilter() {
  const f = State.filters;
  State.filtered = State.allData.filter(r => {
    const brand    = r.brand || r.Brand || (r.campaignId || '').replace(/-\d+$/, '') || '';
    const zone     = r.placementId || r.zone || r.Zone || '';
    const audience = r.audienceSegment || r['Audience Segment'] || r.channel || '';
    const date     = r.date || r.Date || '';

    if (f.brand    && brand !== f.brand)       return false;
    if (f.zone     && zone !== f.zone)         return false;
    if (f.audience && audience !== f.audience) return false;
    if (f.startDate && date < f.startDate)     return false;
    if (f.endDate   && date > f.endDate)       return false;
    return true;
  });

  els.filteredCount.textContent = fmt(State.filtered.length);
}

/* ── Topbar stats ───────────────────────────────────────────────── */
function updateTopbarStats() {
  els.totalRows.textContent = fmt(State.allData.length);
  const totalSpend = State.allData.reduce((s, r) => s + (r.spend || r.spendVnd || r['Spend VND'] || 0), 0);
  els.totalSpend.textContent = fmtVND(totalSpend);
}

/* ── Tab routing ────────────────────────────────────────────────── */
function switchTab(tab) {
  // Remove active from all tabs
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('on'));

  document.querySelector(`[data-tab="${tab}"]`).classList.add('on');
  document.getElementById('p-' + tab).classList.add('on');

  State.activeTab = tab;
  renderActiveTab();
}

function renderActiveTab() {
  const tab = State.activeTab;
  if (State.allData.length === 0) return; // no data yet

  const utils = { fmt, fmtPct, fmtVND, fmtK, COLORS, alpha, registerChart, destroyChart };

  if (tab === 'op') {
    renderDailyOps(State, utils);
  } else if (tab === 'aw') {
    renderAwareness(State, utils);
  } else if (tab === 'co') {
    renderConsideration(State, utils);
  } else if (tab === 'cv') {
    renderConversion(State, utils);
  } else if (tab === 'rt') {
    renderRetention(State, utils);
  } else if (tab === 'ex') {
    renderExecutive(State, utils);
  }
}

/* ── Event listeners ────────────────────────────────────────────── */
function bindEvents() {
  // Tab clicks
  els.tabs.addEventListener('click', e => {
    const btn = e.target.closest('[data-tab]');
    if (!btn) return;
    switchTab(btn.dataset.tab);
  });

  // Apply filter
  els.btnApply.addEventListener('click', () => {
    State.filters = {
      brand:     els.fBrand.value,
      zone:      els.fZone.value,
      audience:  els.fAudience.value,
      startDate: els.fStart.value,
      endDate:   els.fEnd.value
    };
    applyClientFilter();
    renderActiveTab();
  });

  // Reset filter
  els.btnReset.addEventListener('click', () => {
    els.fBrand.value    = '';
    els.fZone.value     = '';
    els.fAudience.value = '';
    els.fStart.value    = '';
    els.fEnd.value      = '';
    State.filters = { brand: '', zone: '', audience: '', startDate: '', endDate: '' };
    applyClientFilter();
    renderActiveTab();
  });

  // Retry button
  els.btnRetry.addEventListener('click', () => {
    loadAll();
  });
}

/* ── Boot ───────────────────────────────────────────────────────── */
async function boot() {
  bindEvents();
  checkConnection();
  await loadAll();

  // Re-check connection every 30s
  setInterval(checkConnection, 30000);
}

boot();
