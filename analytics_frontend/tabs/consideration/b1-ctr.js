/**
 * consideration/b1-ctr.js
 * B1 — CTR Trend by Placement (multi-line) + CTR vs CPM Scatter
 * Use-case: Which placements drive engagement? Is higher cost buying better CTR?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}
function fmtK(v) {
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'K';
  return String(Math.round(v));
}

/* ── B1-a: CTR Trend by Placement (top 5) ───────────────────────── */
export function drawCtrTrend(rows, utils) {
  const { alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_co_ctr_trend');

  // Top 5 placements by total impressions
  const plImp = {};
  rows.forEach(r => { plImp[r.zone] = (plImp[r.zone] || 0) + r.impressions; });
  const top5 = Object.entries(plImp).sort((a, b) => b[1] - a[1]).slice(0, 5).map(e => e[0]);

  const dates = [...new Set(rows.map(r => r.date))].sort();

  const datasets = top5.map((pl, i) => {
    const color = COLORS[i % COLORS.length];
    const data = dates.map(d => {
      const recs = rows.filter(r => r.date === d && r.zone === pl);
      if (!recs.length) return null;
      const imp = recs.reduce((s, r) => s + r.impressions, 0);
      const clk = recs.reduce((s, r) => s + r.clicks, 0);
      return imp > 0 ? +(clk / imp * 100).toFixed(3) : null;
    });
    return {
      label: pl,
      data,
      borderColor: color,
      backgroundColor: alpha(color, 0.1),
      borderWidth: 2,
      pointRadius: 2.5,
      tension: 0.3,
      fill: false,
      spanGaps: true
    };
  });

  const canvas = el('ch_co_ctr_trend');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: { labels: dates.map(d => d.slice(5)), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 10 }, boxWidth: 12 } },
        tooltip: { callbacks: { label: ctx => ctx.raw !== null ? ` ${ctx.dataset.label}: ${ctx.raw.toFixed(2)}%` : null } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: { ticks: { font: { size: 10 }, callback: v => v.toFixed(2) + '%' } }
      }
    }
  });
  registerChart('ch_co_ctr_trend', chart);

  // Insight
  const ic = el('ic_co_ctr_trend'), ins = el('ins_co_ctr_trend');
  if (ic && ins && top5.length > 0) {
    const plCtrs = top5.map(pl => {
      const recs = rows.filter(r => r.zone === pl);
      const imp = recs.reduce((s, r) => s + r.impressions, 0);
      const clk = recs.reduce((s, r) => s + r.clicks, 0);
      return { pl, ctr: imp > 0 ? clk / imp * 100 : 0 };
    }).sort((a, b) => b.ctr - a.ctr);
    ic.className = 'insight-ic good'; ic.textContent = '✓';
    ins.innerHTML = `<b>${plCtrs[0].pl}</b> leads with CTR <b>${plCtrs[0].ctr.toFixed(2)}%</b>. `
      + `<b>${plCtrs[plCtrs.length - 1].pl}</b> trails at <b>${plCtrs[plCtrs.length - 1].ctr.toFixed(2)}%</b> — consider reallocating budget toward top performers.`;
  }
}

/* ── B1-b: CTR vs CPM Scatter ───────────────────────────────────── */
export function drawCtrVsCpmScatter(rows, utils) {
  const { alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_co_scatter');

  // One point per placement: x=avg CPM, y=avg CTR, size=impressions
  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { imp: 0, clk: 0, cpmSum: 0, n: 0 };
    plMap[pl].imp    += r.impressions;
    plMap[pl].clk    += r.clicks;
    plMap[pl].cpmSum += r.cpm;
    plMap[pl].n++;
  });

  // Group by channel for coloring
  const chMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    chMap[pl] = r.channel || 'unknown';
  });
  const channels = [...new Set(Object.values(chMap))];

  const datasets = channels.map((ch, i) => {
    const color = COLORS[i % COLORS.length];
    const pts = Object.entries(plMap)
      .filter(([pl]) => chMap[pl] === ch && plMap[pl].imp > 0)
      .map(([pl, d]) => ({
        x: +(d.cpmSum / d.n / 1000).toFixed(1), // CPM in K₫
        y: +(d.clk / d.imp * 100).toFixed(3),
        r: Math.max(5, Math.min(20, Math.sqrt(d.imp / 50000))),
        label: pl
      }));
    return {
      label: ch,
      data: pts,
      backgroundColor: alpha(color, 0.7),
      borderColor: color,
      borderWidth: 1
    };
  });

  const canvas = el('ch_co_scatter');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bubble',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { font: { size: 10 }, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const pt = ctx.raw;
              return [`${ctx.dataset.label}`, `CPM: ₫${(pt.x * 1000).toLocaleString('vi-VN')}`, `CTR: ${pt.y.toFixed(2)}%`];
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Avg CPM (K₫)', font: { size: 10 } },
          ticks: { font: { size: 10 }, callback: v => '₫' + fmtK(v * 1000) }
        },
        y: {
          title: { display: true, text: 'CTR %', font: { size: 10 } },
          ticks: { font: { size: 10 }, callback: v => v.toFixed(2) + '%' }
        }
      }
    }
  });
  registerChart('ch_co_scatter', chart);

  const ic = el('ic_co_scatter'), ins = el('ins_co_scatter');
  if (ic && ins) {
    ic.className = 'insight-ic'; ic.textContent = 'i';
    ins.innerHTML = `Each bubble = one placement. <b>Upper-left</b> = low CPM + high CTR (best efficiency). <b>Lower-right</b> = high cost + low engagement (review for pause or renegotiation).`;
  }
}
