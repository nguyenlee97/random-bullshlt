/**
 * Closed-loop local smoke test.
 *
 * Run from the repository root after `docker compose up -d --build`:
 *   node backend/seed/local-ad-stack-smoke.js
 *   node backend/seed/local-ad-stack-smoke.js --keep
 *
 * Creates an active disposable campaign on an unused placement, verifies that
 * the local mock site is reachable and the local ad server returns that exact
 * campaign, records one impression, then soft-deletes the campaign and proves
 * it is no longer served.
 */

const API_BASE = process.env.LOCAL_BACKEND_URL || 'http://localhost:3000/api';
const KEEP_ORDER = process.argv.includes('--keep');

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${options.method || 'GET'} ${path}: ${response.status} ${JSON.stringify(body)}`);
  return body;
}

function tomorrow() {
  const value = new Date(Date.now() + 24 * 60 * 60 * 1000);
  return value.toISOString().slice(0, 10);
}

async function main() {
  const [catalog, orders] = await Promise.all([request('/zones'), request('/orders')]);
  const booked = new Set(
    orders
      .filter((order) => ['active', 'pending'].includes(order.status))
      .flatMap((order) => order.placements || [])
  );
  const zone = (catalog.placements || []).find((item) => item.siteUrl && !booked.has(item.id));
  if (!zone) throw new Error('No unbooked local mock-site placement is available for the smoke test.');

  const isSkin = zone.format === 'skin' || zone.size === 'skin';
  const creative = {
    name: 'local-stack-smoke.png',
    size: isSkin ? 'skin' : zone.size,
    format: isSkin ? 'skin' : zone.format,
    url: isSkin
      ? 'http://localhost:5176/ad-pic/Background.png'
      : 'http://localhost:5176/ad-pic/top-banner.jpg',
    zones: [zone.id],
    groupId: 'local-smoke',
  };
  let order;
  let verified = false;
  try {
    order = await request('/orders', {
      method: 'POST',
      body: JSON.stringify({
        brand: 'Local Stack Smoke', advertiser: 'Advertising Agent QA',
        objective: 'awareness', status: 'active', budget: 1,
        startDate: new Date().toISOString().slice(0, 10), endDate: tomorrow(),
        creative, creatives: [creative], placements: [zone.id],
        targeting: {}, dmp: { include: [], exclude: [] },
        idempotencyKey: `local-stack-smoke:${Date.now()}`,
      }),
    });

    const siteResponse = await fetch(zone.siteUrl);
    if (!siteResponse.ok) throw new Error(`Mock site ${zone.siteUrl} returned ${siteResponse.status}`);

    const delivery = await request(`/ads/check?zone=${encodeURIComponent(zone.id)}&site=local-smoke`);
    if (delivery.ad?.campaignId !== order.id) {
      throw new Error(`Expected ${order.id}, received ${delivery.ad?.campaignId || 'no ad'}`);
    }
    if (delivery.ad?.creative?.url !== creative.url) {
      throw new Error('Delivered creative does not match the campaign creative.');
    }
    await request('/ads/impression', {
      method: 'POST',
      body: JSON.stringify({ campaignId: order.id, placementId: zone.id, siteId: 'local-smoke' }),
    });

    if (KEEP_ORDER) {
      console.log(`OPEN_MOCK_SITE=${zone.siteUrl}`);
      console.log(`ORDER_ID=${order.id}`);
      console.log(`CLEANUP=powershell -Command \"Invoke-RestMethod -Method Delete -Uri '${API_BASE}/orders/${order.id}'\"`);
    }

    console.log(`✅ AdsPilot order ${order.id} created in local MongoDB`);
    console.log(`✅ Mock site reachable: ${zone.siteUrl}`);
    console.log(`✅ Ad delivered for ${zone.id}: ${delivery.ad.creative.url}`);
    console.log('✅ Impression accepted by the local backend');
    verified = true;
  } finally {
    if (order?.id && (!KEEP_ORDER || !verified)) {
      await request(`/orders/${encodeURIComponent(order.id)}`, { method: 'DELETE' });
      const afterDelete = await request(`/ads/check?zone=${encodeURIComponent(zone.id)}&site=local-smoke`);
      if (afterDelete.ad?.campaignId === order.id) {
        throw new Error(`Soft-deleted campaign ${order.id} is still being served.`);
      }
      console.log(`✅ Disposable order ${order.id} removed from ad serving`);
    }
  }
}

main().catch((error) => {
  console.error(`❌ Local ad stack smoke failed: ${error.message}`);
  process.exitCode = 1;
});
