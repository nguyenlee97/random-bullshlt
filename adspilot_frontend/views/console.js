/**
 * views/console.js — read-only API activity log
 */

async function renderApiConsole() {
  setMain(`
    <div class="crumb"><b>API Console</b></div>
    <div class="callout info">
      <b>Live log</b> — Real API calls recorded by the backend middleware.
      This production console is read-only; administrative and test actions are not exposed here.
    </div>
    <div style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
      <button class="btn sm sec" onclick="refreshLog()">↻ Refresh</button>
      <span style="margin-left:auto;font-size:11.5px;color:var(--muted)">
        Last 100 entries — newest first
      </span>
    </div>
    <div class="console" id="consoleBox">
      <div class="empty-log">Loading log...</div>
    </div>
  `);
  refreshLog();
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
