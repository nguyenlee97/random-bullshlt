/**
 * Smoke test — hits key endpoints and prints results.
 * Run: node seed/smoke-test.js
 */
const http = require('http');

const BASE = 'http://localhost:3000';

function get(path) {
  return new Promise((resolve, reject) => {
    http.get(BASE + path, (res) => {
      let data = '';
      res.on('data', (c) => (data += c));
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, body: data }); }
      });
    }).on('error', reject);
  });
}

async function main() {
  const tests = [
    { label: 'Health',            path: '/api/health' },
    { label: 'Orders (all)',      path: '/api/orders' },
    { label: 'Zones (summary)',   path: '/api/zones' },
    { label: 'DMP (first 3)',     path: '/api/dmp/attributes?limit=3' },
    { label: 'Targeting options', path: '/api/targeting/options' },
    { label: 'Analytics summary', path: '/api/analytics/summary' },
    { label: 'Admin stats',       path: '/api/admin/stats' },
  ];

  for (const t of tests) {
    try {
      const r = await get(t.path);
      let preview = '';
      if (Array.isArray(r.body))       preview = `array[${r.body.length}]`;
      else if (typeof r.body === 'object') preview = JSON.stringify(r.body).slice(0, 120);
      else                             preview = String(r.body).slice(0, 120);
      console.log(`\n✅  [${r.status}] ${t.label} (${t.path})`);
      console.log(`    ${preview}`);
    } catch (err) {
      console.log(`\n❌  ${t.label}: ${err.message}`);
    }
  }
  console.log('\n--- Done ---\n');
}

main();
