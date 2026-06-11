/**
 * api.js — API client wrapper for AdsPilot Frontend
 * All fetch() calls to backend at localhost:3000
 */

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:3000/api'
  : 'https://api.pawgrammers.io.vn/api';


const Api = (() => {
  // ── Helpers ────────────────────────────────────────────────────────────────

  async function request(method, path, body) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    try {
      const res = await fetch(API_BASE + path, opts);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      return json;
    } catch (err) {
      console.error(`[API] ${method} ${path}`, err.message);
      throw err;
    }
  }

  const get    = (path)        => request('GET',    path);
  const post   = (path, body)  => request('POST',   path, body);
  const put    = (path, body)  => request('PUT',    path, body);
  const del    = (path)        => request('DELETE', path);

  // ── Zone Catalog ──────────────────────────────────────────────────────────

  /** @returns {Promise<{groups, channels, placements}>} */
  function listZones() {
    return get('/zones');
  }

  /** @returns {Promise<Array>} flat list of placements */
  function listPlacements() {
    return get('/zones/placements');
  }

  // ── Targeting ─────────────────────────────────────────────────────────────

  /** @returns {Promise<{geo, age, gender, deviceOS, deviceBrand, marital, parental, education, income, career, interest, weather}>} */
  function listTargetingOptions() {
    return get('/targeting/options');
  }

  // ── DMP Attributes ────────────────────────────────────────────────────────

  /**
   * @param {object} [opts] - { q, type, category, limit }
   * @returns {Promise<{count, items}>}
   */
  function listDmpAttributes(opts = {}) {
    const params = new URLSearchParams();
    if (opts.q)        params.set('q',        opts.q);
    if (opts.type)     params.set('type',     opts.type);
    if (opts.category) params.set('category', opts.category);
    if (opts.limit)    params.set('limit',    opts.limit);
    const qs = params.toString();
    return get('/dmp/attributes' + (qs ? '?' + qs : ''));
  }

  // ── Orders ────────────────────────────────────────────────────────────────

  /** @param {{status?,brand?}} [filter] */
  function listOrders(filter = {}) {
    const params = new URLSearchParams();
    if (filter.status) params.set('status', filter.status);
    if (filter.brand)  params.set('brand',  filter.brand);
    const qs = params.toString();
    return get('/orders' + (qs ? '?' + qs : ''));
  }

  /** @param {string} id */
  function getOrder(id) {
    return get('/orders/' + encodeURIComponent(id));
  }

  /** @param {object} payload */
  function createOrder(payload) {
    return post('/orders', payload);
  }

  /** @param {string} id @param {object} patch */
  function updateOrder(id, patch) {
    return put('/orders/' + encodeURIComponent(id), patch);
  }

  /** @param {string} id */
  function pauseOrder(id) {
    return post('/orders/' + encodeURIComponent(id) + '/pause');
  }

  /** @param {string} id */
  function resumeOrder(id) {
    return post('/orders/' + encodeURIComponent(id) + '/resume');
  }

  /** @param {string} id */
  function archiveOrder(id) {
    return post('/orders/' + encodeURIComponent(id) + '/archive');
  }

  /** @param {string} id */
  function deleteOrder(id) {
    return del('/orders/' + encodeURIComponent(id));
  }

  // ── Audience Estimate ─────────────────────────────────────────────────────

  /**
   * @param {object} targeting - { geo, age, gender, deviceOS, income, education, interest, dmpInclude }
   * @returns {Promise<{size, low, high, totalPop}>}
   */
  function estimateAudience(targeting) {
    return post('/audience/estimate', targeting);
  }

  // ── Logs ──────────────────────────────────────────────────────────────────

  /** @param {{limit?,method?,path?}} [opts] */
  function getLogs(opts = {}) {
    const params = new URLSearchParams();
    if (opts.limit)  params.set('limit',  opts.limit);
    if (opts.method) params.set('method', opts.method);
    if (opts.path)   params.set('path',   opts.path);
    const qs = params.toString();
    return get('/logs' + (qs ? '?' + qs : ''));
  }

  function clearLogs() {
    return del('/logs');
  }

  // ── Admin ─────────────────────────────────────────────────────────────────

  function resetDb() {
    return post('/admin/reset');
  }

  function getStats() {
    return get('/admin/stats');
  }

  function healthCheck() {
    return get('/health');
  }

  // ── Analytics ─────────────────────────────────────────────────────────────

  function getAnalyticsSummary() {
    return get('/analytics/summary');
  }

  return {
    listZones, listPlacements,
    listTargetingOptions,
    listDmpAttributes,
    listOrders, getOrder, createOrder, updateOrder,
    pauseOrder, resumeOrder, archiveOrder, deleteOrder,
    estimateAudience,
    getLogs, clearLogs,
    resetDb, getStats, healthCheck,
    getAnalyticsSummary,
  };
})();

window.Api = Api;
