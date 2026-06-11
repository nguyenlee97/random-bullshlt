/**
 * views/console.js — API Console (Activity Log + Test Endpoints)
 */

let _consoleTab = 'log';

async function renderApiConsole() {
  setMain(`
    <div class="crumb"><b>API Console</b></div>
    <div class="callout info">
      <b>Live log</b> — Real API calls recorded by the backend middleware.
      Agent integrates via REST endpoints at <code>localhost:3000/api/</code>
      (see <a onclick="navTo('docs')">API Docs</a> for full reference).
    </div>
    <div class="api-tabs">
      <button id="tabLog"  class="on" onclick="switchConsoleTab('log')">📋 Activity Log</button>
      <button id="tabTest"          onclick="switchConsoleTab('test')">🧪 Test Endpoints</button>
    </div>
    <div id="apiPanel"></div>
  `);
  switchConsoleTab(_consoleTab);
}

async function switchConsoleTab(t) {
  _consoleTab = t;
  const tabLog  = document.getElementById('tabLog');
  const tabTest = document.getElementById('tabTest');
  if (tabLog)  tabLog.classList.toggle('on',  t === 'log');
  if (tabTest) tabTest.classList.toggle('on', t === 'test');

  const panel = document.getElementById('apiPanel');
  if (!panel) return;

  if (t === 'log') {
    panel.innerHTML = `
      <div style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
        <button class="btn sm sec" onclick="clearAndRefreshLog()">🗑 Clear log</button>
        <button class="btn sm sec" onclick="refreshLog()">↻ Refresh</button>
        <span style="margin-left:auto;font-size:11.5px;color:var(--muted)">
          Last 100 entries — newest first
        </span>
      </div>
      <div class="console" id="consoleBox">
        <div class="empty-log">Loading log...</div>
      </div>`;
    refreshLog();
  } else {
    panel.innerHTML = `
      <div class="card">
        <div class="head">🧪 Quick Test Endpoints</div>
        <div class="body">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <button class="btn sec sm" id="btnListOrders"    onclick="runTest('listOrders')">GET /api/orders</button>
            <button class="btn sec sm" id="btnListZones"     onclick="runTest('listZones')">GET /api/zones</button>
            <button class="btn sec sm" id="btnTargeting"     onclick="runTest('listTargeting')">GET /api/targeting/options</button>
            <button class="btn sec sm" id="btnDmp"           onclick="runTest('listDmp')">GET /api/dmp/attributes</button>
            <button class="btn sec sm" id="btnHealth"        onclick="runTest('health')">GET /api/health</button>
            <button class="btn sec sm" id="btnStats"         onclick="runTest('stats')">GET /api/admin/stats</button>
            <button class="btn sec sm" id="btnEstimate"      onclick="runTest('estimate')">POST /api/audience/estimate</button>
            <button class="btn sec sm" id="btnCreateSample"  onclick="runTest('createSample')">POST /api/orders (sample)</button>
            <button class="btn sec sm" id="btnPauseLast"     onclick="runTest('pauseLast')">POST /api/orders/:id/pause</button>
            <button class="btn sec sm" id="btnLogs"          onclick="runTest('getLogs')">GET /api/logs</button>
            <button class="btn danger sm" style="grid-column:1/-1" onclick="confirmReset()">🔴 POST /api/admin/reset (reset DB)</button>
          </div>
          <div style="margin-top:14px">
            <b style="font-size:12px">Result:</b>
            <pre id="testResult" style="background:#0d1929;color:#cbe0d5;padding:12px;border-radius:5px;font-size:11.5px;font-family:ui-monospace,monospace;max-height:340px;overflow:auto;margin-top:6px;line-height:1.55">Click a button above to test an endpoint...</pre>
          </div>
        </div>
      </div>`;
  }
}

async function refreshLog() {
  const box = document.getElementById('consoleBox');
  if (!box) return;
  try {
    const logs = await Api.getLogs({ limit: 100 });
    if (!logs.length) {
      box.innerHTML = `<div class="empty-log">No API calls logged yet. Create or edit an order to generate activity.</div>`;
      return;
    }
    box.innerHTML = logs.map(l => {
      const method = l.method || 'GET';
      const ts     = typeof l.ts === 'string' ? l.ts.slice(0,19).replace('T',' ') : '';
      const path   = l.path   || l.url || '';
      const body   = l.body   ? JSON.stringify(l.body).slice(0, 200) : null;
      const resp   = l.resp !== undefined ? JSON.stringify(l.resp).slice(0, 200) : (l.status ? String(l.status) : null);
      return `
        <div class="ln">
          <span class="ts">${escHTML(ts)}</span>
          <span class="mt ${method}">${method}</span>
          <span class="pa">${escHTML(path)}</span>
          ${body ? `<span class="res">body: ${escHTML(body)}${JSON.stringify(l.body).length > 200 ? '…' : ''}</span>` : ''}
          ${resp ? `<span class="res">→ ${escHTML(resp)}${JSON.stringify(l.resp || l.status || '').length > 200 ? '…' : ''}</span>` : ''}
        </div>`;
    }).join('');
  } catch (e) {
    box.innerHTML = `<div class="empty-log" style="color:#c0392b">Error loading logs: ${escHTML(e.message)}</div>`;
  }
}

async function clearAndRefreshLog() {
  try {
    await Api.clearLogs();
    toast('Log cleared');
    refreshLog();
  } catch (e) {
    toast('Error clearing log: ' + e.message, true);
  }
}

async function runTest(name) {
  const el = document.getElementById('testResult');
  if (el) el.textContent = 'Running…';
  try {
    let r;
    if (name === 'listOrders')    r = await Api.listOrders();
    else if (name === 'listZones')r = await Api.listZones();
    else if (name === 'listTargeting') r = await Api.listTargetingOptions();
    else if (name === 'listDmp')  r = await Api.listDmpAttributes({ limit: 20 });
    else if (name === 'health')   r = await Api.healthCheck();
    else if (name === 'stats')    r = await Api.getStats();
    else if (name === 'estimate') r = await Api.estimateAudience({
      geo: ['Hà Nội', 'TP.HCM'],
      age: ['25-34', '35-44'],
      deviceOS: ['Android', 'iOS'],
      dmpInclude: ['INT001', 'INT002'],
    });
    else if (name === 'createSample') r = await Api.createOrder({
      brand: 'Test Brand ' + Math.floor(Math.random() * 900 + 100),
      advertiser: 'Demo Co.',
      objective: 'awareness',
      budget: 100_000_000,
      daily: 8_000_000,
      rate: 35_000,
      rateType: 'CPM',
      startDate: '2026-06-15',
      endDate: '2026-07-15',
      creative: { name: 'Demo Banner', size: '720x1280', url: '' },
      placements: ['PulseNews.Home.Inpage1'],
      targeting: { geo: ['TP.HCM'], age: ['25-34'], gender: [], deviceOS: ['Android'], marital: [], parental: [], education: [], income: [], career: [], interest: [], weather: [] },
      dmp: { include: [], exclude: [] },
    });
    else if (name === 'pauseLast') {
      const orders = await Api.listOrders();
      const target = orders.find(o => o.status === 'active' || o.status === 'pending');
      if (!target) { r = 'No active/pending order found'; }
      else r = await Api.pauseOrder(target.id);
    }
    else if (name === 'getLogs') r = await Api.getLogs({ limit: 10 });

    if (el) el.textContent = JSON.stringify(r, null, 2);
    toast('✓ ' + name + ' called');
  } catch (e) {
    if (el) el.textContent = 'Error: ' + e.message;
    toast('Error: ' + e.message, true);
  }
}

async function confirmReset() {
  if (!confirm('Reset database to seed data? This will delete all orders you created.')) return;
  try {
    const r = await Api.resetDb();
    const el = document.getElementById('testResult');
    if (el) el.textContent = JSON.stringify(r, null, 2);
    toast('✓ Database reset to seed data');
    zonesCache    = null;
    targetingCache = null;
    dmpCache      = null;
  } catch (e) {
    toast('Reset failed: ' + e.message, true);
  }
}
