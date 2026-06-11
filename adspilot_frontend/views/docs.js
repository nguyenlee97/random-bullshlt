/**
 * views/docs.js — API Docs reference view
 */

function renderDocs() {
  const endpoints = [
    { m: 'GET',    p: '/api/health',                    d: 'Health check — confirms backend is up.' },
    { m: 'GET',    p: '/api/zones',                     d: 'Zone catalog — groups, channels, and all placements with reach/CPM/CTR.' },
    { m: 'GET',    p: '/api/zones/placements',          d: 'Flat list of all placements only.' },
    { m: 'GET',    p: '/api/zones/placements/:id',      d: 'Single placement by ID.' },
    { m: 'GET',    p: '/api/targeting/options',         d: 'All targeting dimension values (age, gender, geo, deviceOS, income, etc.).' },
    { m: 'GET',    p: '/api/dmp/attributes',            d: 'DMP audience library (310 segments). Filterable: ?q=&type=&category=&limit=.' },
    { m: 'GET',    p: '/api/orders',                    d: 'List campaigns. Filter: ?status=active&brand=Nike.' },
    { m: 'GET',    p: '/api/orders/:id',                d: 'Single campaign detail.' },
    { m: 'POST',   p: '/api/orders',                    d: 'Create campaign. Returns created order + any zone-format warnings[].' },
    { m: 'PUT',    p: '/api/orders/:id',                d: 'Update any fields on a campaign.' },
    { m: 'POST',   p: '/api/orders/:id/pause',          d: "Set campaign status → 'paused'." },
    { m: 'POST',   p: '/api/orders/:id/resume',         d: "Set campaign status → 'active'." },
    { m: 'POST',   p: '/api/orders/:id/archive',        d: "Set campaign status → 'archived'." },
    { m: 'DELETE', p: '/api/orders/:id',                d: 'Permanently delete a campaign.' },
    { m: 'POST',   p: '/api/audience/estimate',         d: 'Estimate audience size. Body: { geo, age, gender, deviceOS, income, education, interest, dmpInclude }. Returns { size, low, high, totalPop }.' },
    { m: 'GET',    p: '/api/analytics/summary',         d: 'Top-level analytics summary (impressions, clicks, CTR, spend).' },
    { m: 'GET',    p: '/api/analytics/data',            d: 'Full analytics records. Filter: ?campaign=&placement=&from=&to=.' },
    { m: 'GET',    p: '/api/analytics/by-campaign',     d: 'Analytics aggregated per campaign.' },
    { m: 'GET',    p: '/api/analytics/by-placement',    d: 'Analytics aggregated per placement.' },
    { m: 'GET',    p: '/api/logs',                      d: 'API call log. Filter: ?limit=100&method=POST&path=/orders.' },
    { m: 'DELETE', p: '/api/logs',                      d: 'Clear all API logs.' },
    { m: 'GET',    p: '/api/admin/stats',               d: 'DB stats: counts per collection.' },
    { m: 'POST',   p: '/api/admin/reset',               d: 'Reset DB to seed data.' },
  ];

  const quickStart = `// 1. Fetch catalog
const zones      = await fetch('/api/zones').then(r=>r.json());
const targeting  = await fetch('/api/targeting/options').then(r=>r.json());
const dmpAttrs   = await fetch('/api/dmp/attributes?limit=50').then(r=>r.json());

// 2. Estimate audience before creating campaign
const estimate = await fetch('/api/audience/estimate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    geo: ['Hà Nội', 'TP.HCM'], age: ['25-34', '35-44'],
    deviceOS: ['Android', 'iOS'], income: ['Top 5-10%'],
    interest: ['Travel', 'Air travel'],
    dmpInclude: ['INT001', 'INT002']
  })
}).then(r=>r.json());
// → { size: 1200000, low: 1020000, high: 1380000, totalPop: 60000000 }

// 3. Create campaign
const order = await fetch('/api/orders', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    brand: 'Brand A',
    advertiser: 'Brand A Vietnam',
    objective: 'awareness',
    status: 'active',
    budget: 425_000_000,
    daily:   43_000_000,
    rate:    36960,
    rateType: 'CPM',
    startDate: '2026-06-10',
    endDate:   '2026-07-10',
    creative: { name: 'BrandA Summer', size: '720x1280', url: 'https://cdn.../banner.jpg' },
    placements: ['PulseNews.Home.Inpage1', 'VibeTV.ShortVideo.Infeed.Fullscreen1'],
    targeting: {
      geo: ['Hà Nội', 'TP.HCM'], age: ['25-34', '35-44'],
      deviceOS: ['Android', 'iOS'], income: ['Top 5-10%'],
      interest: ['Travel', 'Air travel'],
      gender: [], marital: [], parental: [], education: [], career: [], weather: []
    },
    dmp: { include: ['INT001', 'INT002'], exclude: [] }
  })
}).then(r=>r.json());
// → { id: 'ORD-2026-004', status: 'active', warnings: [], ... }

// 4. Lifecycle operations
await fetch('/api/orders/' + order.id + '/pause',   { method: 'POST' });
await fetch('/api/orders/' + order.id + '/resume',  { method: 'POST' });
await fetch('/api/orders/' + order.id,              { method: 'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ daily: 55_000_000 }) });
await fetch('/api/orders/' + order.id + '/archive', { method: 'POST' });`;

  setMain(`
    <div class="crumb"><b>API Docs</b></div>
    <div class="callout info">
      <b>REST API reference</b> — Backend running at <code>http://localhost:3000</code>.
      All endpoints return JSON. POST/PUT bodies must use <code>Content-Type: application/json</code>.
      The <code>warnings[]</code> array on order responses is non-blocking — it signals format/size mismatches between creative and selected zones.
    </div>

    <div class="card">
      <div class="head">📚 Endpoints (${endpoints.length})</div>
      <div class="body">
        ${endpoints.map(e => `
          <div class="endpoint">
            <span class="mt ${e.m}">${e.m}</span><code>${escHTML(e.p)}</code>
            <p>${escHTML(e.d)}</p>
          </div>`).join('')}
      </div>
    </div>

    <div class="card">
      <div class="head">💡 Quick Start (for AI Agent)</div>
      <div class="body">
        <pre style="background:#0d1929;color:#cbe0d5;padding:14px;border-radius:5px;font-size:12px;line-height:1.65;font-family:ui-monospace,monospace;overflow:auto">${escHTML(quickStart)}</pre>
      </div>
    </div>

    <div class="card">
      <div class="head">📦 Order Payload Schema</div>
      <div class="body">
        <pre style="background:#f3f5f8;padding:12px;border-radius:5px;font-size:12px;line-height:1.65;font-family:ui-monospace,monospace;overflow:auto">${escHTML(`{
  "brand":       "string (required)",
  "advertiser":  "string",
  "objective":   "awareness | consideration | conversion | retention",
  "status":      "pending | active | paused | draft | archived",
  "budget":      "number (VND, lifetime cap)",
  "daily":       "number (VND, daily cap)",
  "rate":        "number (VND per unit)",
  "rateType":    "CPM | CPC | CPV | FlatFee",
  "startDate":   "YYYY-MM-DD",
  "endDate":     "YYYY-MM-DD",
  "creative": {
    "name":  "string",
    "size":  "WxH (e.g. 720x1280)",
    "url":   "https://cdn.../banner.jpg"
  },
  "placements":  ["PlacementId1", "PlacementId2"],
  "targeting": {
    "geo":        ["Hà Nội", "TP.HCM"],
    "age":        ["25-34", "35-44"],
    "gender":     ["Male", "Female"],
    "deviceOS":   ["Android", "iOS"],
    "deviceBrand":["Samsung", "Apple"],
    "marital":    ["Single", "Married"],
    "parental":   ["Have children", "No children"],
    "education":  ["College & Bachelor", "Master"],
    "income":     ["Top 5-10%", "Top 10-25%"],
    "career":     ["Office Worker", "Student"],
    "interest":   ["Travel", "Fintech"],
    "weather":    ["Sunny", "Rain"]
  },
  "dmp": {
    "include": ["INT001", "BEH003"],
    "exclude": ["INT010"]
  }
}`)}</pre>
      </div>
    </div>
  `);
}
