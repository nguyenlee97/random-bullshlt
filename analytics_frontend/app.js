/**
 * app.js — campaign-aware analytics dashboard
 *
 * Aggregate mode renders the complete analytics record catalog.
 * Campaign mode uses the same campaign record endpoint as the Agent UI so both
 * surfaces chart the same authoritative dataset. Generated analysis stays in
 * the Agent UI.
 */
import {
  fetchData,
  fetchHealth,
  fetchOrders,
  fetchReportData
} from './api.js?v=1.1.4';
import {
  campaignOptions,
  filterRecords,
  requestedCampaignId
} from './campaign-data.js?v=1.1.4';
import { render as renderDailyOps } from './tabs/daily-ops.js?v=1.1.4';
import { render as renderAwareness } from './tabs/awareness.js?v=1.1.4';
import { render as renderConsideration } from './tabs/consideration.js?v=1.1.4';
import { render as renderConversion } from './tabs/conversion.js?v=1.1.4';
import { render as renderRetention } from './tabs/retention.js?v=1.1.4';
import { render as renderExecutive } from './tabs/executive.js?v=1.1.4';

const State = {
  allData: [],
  sourceData: [],
  filtered: [],
  orders: [],
  dataRequest: 0,
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

const $ = id => document.getElementById(id);

const els = {
  loadingOverlay: $('loadingOverlay'),
  loadingText: $('loadingText'),
  errorState: $('errorState'),
  errorMsg: $('errorMsg'),
  totalRows: $('totalRows'),
  totalSpend: $('totalSpend'),
  filteredCount: $('filteredCount'),
  connDot: $('connDot'),
  connLabel: $('connLabel'),
  fBrand: $('fBrand'),
  fZone: $('fZone'),
  fAudience: $('fAudience'),
  fStart: $('fStart'),
  fEnd: $('fEnd'),
  btnApply: $('btnApplyFilter'),
  btnReset: $('btnResetFilter'),
  btnRetry: $('btnRetry'),
  tabs: $('tabs')
};

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
  if (n >= 1_000_000) return '₫' + (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return '₫' + (n / 1_000).toFixed(0) + 'K';
  return '₫' + n;
}

export function fmtK(n) {
  if (!n) return '0';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export const COLORS = [
  '#1f3551', '#2c7fb8', '#5ba33d', '#c98a14', '#6e4cb8',
  '#0d8a8a', '#c54a8a', '#c0392b', '#2980b9', '#27ae60'
];

export function alpha(hex, a) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

async function checkConnection() {
  try {
    await fetchHealth();
    els.connDot.className = 'conn-dot ok';
    els.connLabel.textContent = 'Connected';
  } catch {
    els.connDot.className = 'conn-dot err';
    els.connLabel.textContent = 'Offline';
  }
}

function setLoading(loading, message = 'Loading analytics data…') {
  State.loading = loading;
  els.loadingText.textContent = message;
  els.loadingOverlay.classList.toggle('hidden', !loading);
}

function normalizeArray(result) {
  return Array.isArray(result) ? result : (result?.data || []);
}

function updateUrlCampaign(campaignId) {
  const url = new URL(window.location.href);
  if (campaignId) url.searchParams.set('campaignId', campaignId);
  else url.searchParams.delete('campaignId');
  window.history.replaceState({}, '', url);
}

async function loadAll() {
  setLoading(true);
  els.errorState.classList.add('hidden');

  try {
    const [dataResult, ordersResult] = await Promise.all([
      fetchData(),
      fetchOrders().catch(error => {
        console.warn('[analytics] Campaign labels unavailable:', error);
        return [];
      })
    ]);

    State.allData = normalizeArray(dataResult);
    State.sourceData = State.allData;
    State.orders = normalizeArray(ordersResult);

    const requestedId = requestedCampaignId(window.location.search);
    populateCampaignDropdown(requestedId);

    if (requestedId) {
      els.fBrand.value = requestedId;
      await loadCampaignData(requestedId, { updateUrl: false, showOverlay: false });
    } else {
      State.filters.brand = '';
      populateDimensionDropdowns(State.sourceData);
      applyClientFilter();
      renderActiveTab();
    }
  } catch (error) {
    console.error('[analytics] Load failed:', error);
    els.errorMsg.textContent = error.message || 'The analytics backend is unreachable.';
    els.errorState.classList.remove('hidden');
  } finally {
    setLoading(false);
  }
}

function populateCampaignDropdown(requestedId = '') {
  const options = campaignOptions(State.allData, State.orders, requestedId);
  const current = requestedId || els.fBrand.value;
  els.fBrand.innerHTML = '<option value="">All campaigns (aggregate)</option>';

  for (const item of options) {
    const option = document.createElement('option');
    option.value = item.value;
    option.textContent = item.label;
    option.selected = item.value === current;
    els.fBrand.appendChild(option);
  }
}

function populateDimensionDropdowns(data) {
  const zoneValue = els.fZone.value;
  const audienceValue = els.fAudience.value;
  const zones = [...new Set(data.map(record =>
    record.placementId || record.zone || record.Zone || ''
  ).filter(Boolean))].sort();
  const audiences = [...new Set(data.map(record =>
    record.audienceSegment || record['Audience Segment'] || record.channel || ''
  ).filter(Boolean))].sort();

  fillSelect(els.fZone, zones, 'All placements', zoneValue);
  fillSelect(els.fAudience, audiences, 'All channels', audienceValue);
}

function fillSelect(select, options, placeholder, current = '') {
  select.innerHTML = '';
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = placeholder;
  select.appendChild(defaultOption);

  for (const value of options) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    option.selected = value === current;
    select.appendChild(option);
  }

  if (![...select.options].some(option => option.value === current)) select.value = '';
}

async function loadCampaignData(campaignId, {
  updateUrl = true,
  showOverlay = true
} = {}) {
  const request = ++State.dataRequest;
  State.filters.brand = campaignId;
  els.fBrand.value = campaignId;

  if (updateUrl) updateUrlCampaign(campaignId);

  if (!campaignId) {
    State.sourceData = State.allData;
    populateDimensionDropdowns(State.sourceData);
    applyClientFilter();
    renderActiveTab();
    return;
  }

  if (showOverlay) setLoading(true, `Loading chart data for ${campaignId}…`);

  try {
    const recordsResult = await fetchReportData(campaignId);
    if (request !== State.dataRequest) return;
    State.sourceData = normalizeArray(recordsResult);
  } catch (error) {
    if (request !== State.dataRequest) return;
    console.error(`[analytics] Campaign data load failed for ${campaignId}:`, error);
    State.sourceData = State.allData.filter(record => record.campaignId === campaignId);
  } finally {
    if (request === State.dataRequest) {
      populateDimensionDropdowns(State.sourceData);
      applyClientFilter();
      renderActiveTab();
      if (showOverlay) setLoading(false);
    }
  }
}

function applyClientFilter() {
  State.filtered = filterRecords(State.sourceData, State.filters);
  els.filteredCount.textContent = fmt(State.filtered.length);
  updateTopbarStats();
}

function updateTopbarStats() {
  const data = State.filtered;
  els.totalRows.textContent = fmt(data.length);
  const totalSpend = data.reduce((sum, record) =>
    sum + Number(record.spend || record.spendVnd || record['Spend VND'] || 0), 0);
  els.totalSpend.textContent = fmtVND(totalSpend);
}

function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(button => button.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('on'));

  document.querySelector(`[data-tab="${tab}"]`)?.classList.add('on');
  document.getElementById('p-' + tab)?.classList.add('on');

  State.activeTab = tab;
  renderActiveTab();
}

function renderActiveTab() {
  if (State.loading && State.allData.length === 0) return;

  const utils = { fmt, fmtPct, fmtVND, fmtK, COLORS, alpha, registerChart, destroyChart };
  const renderers = {
    op: renderDailyOps,
    aw: renderAwareness,
    co: renderConsideration,
    cv: renderConversion,
    rt: renderRetention,
    ex: renderExecutive
  };
  renderers[State.activeTab]?.(State, utils);
}

function readFiltersFromControls() {
  State.filters = {
    brand: els.fBrand.value,
    zone: els.fZone.value,
    audience: els.fAudience.value,
    startDate: els.fStart.value,
    endDate: els.fEnd.value
  };
}

function bindEvents() {
  els.tabs.addEventListener('click', event => {
    const button = event.target.closest('[data-tab]');
    if (button) switchTab(button.dataset.tab);
  });

  els.fBrand.addEventListener('change', () => {
    els.fZone.value = '';
    els.fAudience.value = '';
    els.fStart.value = '';
    els.fEnd.value = '';
    State.filters = {
      brand: els.fBrand.value,
      zone: '',
      audience: '',
      startDate: '',
      endDate: ''
    };
    loadCampaignData(els.fBrand.value);
  });

  els.btnApply.addEventListener('click', () => {
    readFiltersFromControls();
    applyClientFilter();
    renderActiveTab();
  });

  els.btnReset.addEventListener('click', () => {
    els.fBrand.value = '';
    els.fZone.value = '';
    els.fAudience.value = '';
    els.fStart.value = '';
    els.fEnd.value = '';
    State.filters = { brand: '', zone: '', audience: '', startDate: '', endDate: '' };
    loadCampaignData('');
  });

  els.btnRetry.addEventListener('click', loadAll);
}

async function boot() {
  bindEvents();
  checkConnection();
  await loadAll();
  setInterval(checkConnection, 30000);
}

boot();
