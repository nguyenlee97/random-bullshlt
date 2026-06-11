/**
 * consideration/b2-clicks.js
 * B2 — Daily Click Volume (stacked by channel) + Top Placements by Clicks table
 * Use-case: Where are clicks coming from and is volume growing or declining?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── B2-a: Daily Click Volume stacked bar by channel ────────────── */
export function drawClickVolume(rows, utils) {
  const { fmt, alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_co_clicks');

  const channels = [...new Set(rows.map(r => r.channel).filter(Boolean))];
  const dates    = [...new Set(rows.map(r => r.date))].sort();

  const datasets = channels.map((ch, i) => {
    const color = COLORS[i % COLORS.length];
    const data = dates.map(d =>
      rows.filter(r => r.date === d && r.channel === ch)
          .reduce((s, r) => s + r.clicks, 0)
    );
    return {
      label: ch,
      data,
      backgroundColor: alpha(color, 0.82),
      stack: 'clicks'
    };
  });

  const canvas = el('ch_co_clicks');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: { labels: dates.map(d => d.slice(5)), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)} clicks` } }
      },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: {
          stacked: true,
          ticks: {
            font: { size: 10 },
            callback: v => v >= 1e3 ? (v / 1e3).toFixed(0) + 'K' : v
          }
        }
      }
    }
  });
  registerChart('ch_co_clicks', chart);

  // Insight: trend
  const ic = el('ic_co_clicks'), ins = el('ins_co_clicks');
  if (ic && ins) {
    const totals = dates.map(d => rows.filter(r => r.date === d).reduce((s, r) => s + r.clicks, 0));
    const mid = Math.floor(totals.length / 2);
    const firstHalf = totals.slice(0, mid).reduce((s, v) => s + v, 0) / Math.max(mid, 1);
    const lastHalf  = totals.slice(mid).reduce((s, v) => s + v, 0) / Math.max(totals.length - mid, 1);
    const trend = lastHalf > firstHalf * 1.1 ? 'growing' : lastHalf < firstHalf * 0.9 ? 'declining' : 'stable';
    ic.className = trend === 'growing' ? 'insight-ic good' : trend === 'declining' ? 'insight-ic bad' : 'insight-ic';
    ic.textContent = trend === 'growing' ? '▲' : trend === 'declining' ? '▼' : 'i';
    ins.innerHTML = `Daily click volume is <b>${trend}</b>. Second-half avg <b>${fmt(Math.round(lastHalf))}</b> vs first-half avg <b>${fmt(Math.round(firstHalf))}</b> clicks/day.`;
  }
}

/* ── B2-b: Top Placements by Clicks table ────────────────────────── */
export function renderTopClicksTable(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = el('co-top-clicks');
  if (!container) return;

  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { imp: 0, clk: 0, spend: 0, conv: 0, ch: r.channel || '' };
    plMap[pl].imp   += r.impressions;
    plMap[pl].clk   += r.clicks;
    plMap[pl].spend += r.spend;
    plMap[pl].conv  += r.conversions;
  });

  const sorted = Object.entries(plMap)
    .map(([pl, d]) => ({
      pl, ch: d.ch,
      imp: d.imp, clk: d.clk, spend: d.spend, conv: d.conv,
      ctr: d.imp > 0 ? d.clk / d.imp * 100 : 0,
      cpc: d.clk > 0 ? d.spend / d.clk : 0
    }))
    .sort((a, b) => b.clk - a.clk)
    .slice(0, 12);

  const pillCtr = ctr => {
    const cls = ctr >= 0.8 ? 'good' : ctr >= 0.4 ? 'watch' : 'bad';
    return `<span class="pill ${cls}">${ctr.toFixed(2)}%</span>`;
  };

  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>#</th>
            <th>Placement</th>
            <th>Channel</th>
            <th class="num">Impressions</th>
            <th class="num">Clicks</th>
            <th class="num">CTR</th>
            <th class="num">Spend</th>
            <th class="num">CPC</th>
            <th class="num">Conv.</th>
          </tr>
        </thead>
        <tbody>
          ${sorted.map((r, i) => `
            <tr>
              <td class="ctr" style="color:var(--muted);font-weight:700">${i + 1}</td>
              <td class="lab">${r.pl}</td>
              <td style="color:var(--muted);font-size:11px">${r.ch}</td>
              <td class="num">${fmt(r.imp)}</td>
              <td class="num" style="font-weight:700;color:var(--navy)">${fmt(r.clk)}</td>
              <td class="num">${pillCtr(r.ctr)}</td>
              <td class="num">${fmtVND(r.spend)}</td>
              <td class="num">${fmtVND(r.cpc)}</td>
              <td class="num">${fmt(r.conv)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}
