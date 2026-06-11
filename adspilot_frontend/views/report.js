/**
 * views/report.js — Report overview view
 */

async function renderReport() {
  showLoading();
  let orders = [];
  try {
    orders = await Api.listOrders();
  } catch (e) {
    setMain(`<div class="card"><div class="body placeholder"><div class="ph-icon">⚠️</div><h3>Could not load report</h3><p>${escHTML(e.message)}</p></div></div>`);
    return;
  }

  const totBudget = orders.reduce((s, o) => s + (o.budget || 0), 0);
  const totDaily  = orders.reduce((s, o) => s + (o.daily  || 0), 0);

  const byStatus = {};
  orders.forEach(o => { byStatus[o.status] = (byStatus[o.status] || 0) + 1; });

  const statusColors = {
    active:   'var(--green)',
    paused:   'var(--amber)',
    pending:  '#a07614',
    draft:    'var(--muted)',
    archived: 'var(--red)',
  };

  const statusEntries = Object.entries(byStatus).sort((a, b) => b[1] - a[1]);

  setMain(`
    <div class="crumb"><b>Report</b> <span class="sep">›</span> <b>Overview</b></div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Orders</div>
        <div class="kpi-value">${orders.length}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Active</div>
        <div class="kpi-value green">${byStatus.active || 0}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Budget</div>
        <div class="kpi-value" style="font-size:18px">${fmtVND(totBudget)}đ</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Daily Spend Cap</div>
        <div class="kpi-value" style="font-size:18px">${fmtVND(totDaily)}đ</div>
      </div>
    </div>

    <div class="card">
      <div class="head">📊 Status Breakdown</div>
      <div class="body">
        ${statusEntries.length ? statusEntries.map(([s, c]) => `
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
            <span class="pill-status ${s}" style="min-width:90px;text-align:center">${s}</span>
            <div style="flex:1;background:#f3f5f8;border-radius:4px;height:14px;overflow:hidden">
              <div style="background:${statusColors[s] || 'var(--navy)'};height:100%;width:${Math.round(c / orders.length * 100)}%;transition:.5s ease"></div>
            </div>
            <span style="font-weight:700;color:var(--navy);min-width:30px;text-align:right">${c}</span>
            <span style="font-size:11px;color:var(--muted);min-width:36px">${Math.round(c / orders.length * 100)}%</span>
          </div>`).join('') : '<p style="color:var(--muted);text-align:center;padding:20px">No orders yet.</p>'}
      </div>
    </div>

    <div class="card">
      <div class="head">💰 Budget Distribution by Order</div>
      <div class="body">
        ${orders.length ? `
          <table class="tbl">
            <thead>
              <tr>
                <th>Order</th><th>Brand</th><th>Status</th>
                <th class="tar">Budget</th><th class="tar">Daily Cap</th><th class="tar">Rate</th><th>Type</th>
              </tr>
            </thead>
            <tbody>
              ${orders.map(o => `
                <tr>
                  <td><b style="color:var(--navy)">${escHTML(o.id)}</b></td>
                  <td>${escHTML(o.brand)}</td>
                  <td><span class="pill-status ${o.status}">${o.status}</span></td>
                  <td class="tar">${fmtVND(o.budget)}đ</td>
                  <td class="tar">${fmtVND(o.daily)}đ</td>
                  <td class="tar">${fmtVND(o.rate)}</td>
                  <td><span class="pill-status pending" style="background:#e6f1fb;color:#185fa5">${escHTML(o.rateType)}</span></td>
                </tr>`).join('')}
            </tbody>
          </table>` : '<p style="color:var(--muted);text-align:center;padding:20px">No orders to display.</p>'}
      </div>
    </div>
  `);
}
