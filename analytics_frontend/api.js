/**
 * api.js — Analytics API client
 * Fetches data from backend at :3000
 * Exposes window.AnalyticsApi
 */

const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const localApiOverride = isLocal
  ? new URLSearchParams(window.location.search).get('apiBase')
  : '';
export const API_BASE = localApiOverride || (
  isLocal ? 'http://localhost:3000/api' : 'https://api.pawgrammers.io.vn/api'
);


async function apiFetch(path, opts = {}) {
  const resp = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

/**
 * GET /api/analytics/data
 * Params: campaignId, placementId, channel, startDate, endDate
 */
export async function fetchData(filters = {}) {
  const params = new URLSearchParams();
  if (filters.campaignId)  params.set('campaignId', filters.campaignId);
  if (filters.placementId) params.set('placementId', filters.placementId);
  if (filters.channel)     params.set('channel', filters.channel);
  if (filters.startDate) params.set('startDate', filters.startDate);
  if (filters.endDate)   params.set('endDate', filters.endDate);
  const qs = params.toString();
  return apiFetch('/analytics/data' + (qs ? '?' + qs : ''));
}

/**
 * GET /api/analytics/summary
 */
export async function fetchSummary(filters = {}) {
  const params = new URLSearchParams();
  if (filters.campaignId) params.set('campaignId', filters.campaignId);
  if (filters.startDate) params.set('startDate', filters.startDate);
  if (filters.endDate)   params.set('endDate', filters.endDate);
  const qs = params.toString();
  return apiFetch('/analytics/summary' + (qs ? '?' + qs : ''));
}

/**
 * GET /api/analytics/by-campaign
 */
export async function fetchByCampaign(filters = {}) {
  const params = new URLSearchParams();
  if (filters.startDate) params.set('startDate', filters.startDate);
  if (filters.endDate)   params.set('endDate', filters.endDate);
  const qs = params.toString();
  return apiFetch('/analytics/by-campaign' + (qs ? '?' + qs : ''));
}

/**
 * GET /api/analytics/by-date
 */
export async function fetchByDate(filters = {}) {
  const params = new URLSearchParams();
  if (filters.campaignId) params.set('campaignId', filters.campaignId);
  if (filters.startDate) params.set('startDate', filters.startDate);
  if (filters.endDate)   params.set('endDate', filters.endDate);
  const qs = params.toString();
  return apiFetch('/analytics/by-date' + (qs ? '?' + qs : ''));
}

/**
 * GET /api/analytics/by-placement
 */
export async function fetchByPlacement(filters = {}) {
  const params = new URLSearchParams();
  if (filters.campaignId) params.set('campaignId', filters.campaignId);
  if (filters.startDate) params.set('startDate', filters.startDate);
  if (filters.endDate)   params.set('endDate', filters.endDate);
  const qs = params.toString();
  return apiFetch('/analytics/by-placement' + (qs ? '?' + qs : ''));
}

/**
 * GET /api/health
 */
export async function fetchHealth() {
  return apiFetch('/health');
}

/**
 * GET /api/orders
 * Used only for human-readable campaign labels in the selector.
 */
export async function fetchOrders() {
  return apiFetch('/orders');
}

/**
 * GET /api/reports/data/:campaignId
 * This is the exact record set consumed by the Agent UI report step.
 */
export async function fetchReportData(campaignId) {
  return apiFetch(`/reports/data/${encodeURIComponent(campaignId)}`);
}
