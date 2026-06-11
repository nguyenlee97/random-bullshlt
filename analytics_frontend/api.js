/**
 * api.js — Analytics API client
 * Fetches data from backend at :3000
 * Exposes window.AnalyticsApi
 */

const BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:3000/api'
  : 'https://api.pawgrammers.io.vn/api';


async function apiFetch(path, opts = {}) {
  const resp = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

/**
 * GET /api/analytics/data
 * Params: brand, zone, audience, startDate, endDate, limit
 */
export async function fetchData(filters = {}) {
  const params = new URLSearchParams();
  if (filters.brand)     params.set('brand', filters.brand);
  if (filters.zone)      params.set('zone', filters.zone);
  if (filters.audience)  params.set('audience', filters.audience);
  if (filters.startDate) params.set('startDate', filters.startDate);
  if (filters.endDate)   params.set('endDate', filters.endDate);
  if (filters.limit)     params.set('limit', filters.limit);
  const qs = params.toString();
  return apiFetch('/analytics/data' + (qs ? '?' + qs : ''));
}

/**
 * GET /api/analytics/summary
 */
export async function fetchSummary(filters = {}) {
  const params = new URLSearchParams();
  if (filters.brand)     params.set('brand', filters.brand);
  if (filters.zone)      params.set('zone', filters.zone);
  if (filters.audience)  params.set('audience', filters.audience);
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
  if (filters.brand)     params.set('brand', filters.brand);
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
  if (filters.brand)     params.set('brand', filters.brand);
  if (filters.zone)      params.set('zone', filters.zone);
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
  if (filters.brand)     params.set('brand', filters.brand);
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
