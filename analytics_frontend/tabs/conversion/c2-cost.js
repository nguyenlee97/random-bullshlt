/**
 * conversion/c2-cost.js
 * C2 — CPA by Placement (horizontal bar) + Spend vs Conversions scatter
 * Use-case: Which placements deliver conversions most cheaply?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── C2-a: CPA by Placement (horizontal bar, sorted ascending) ──── */
export function drawCpaByPlacement(rows, utils) {
  const { alpha, registerChart } = utils;
  destroyIfExists('ch_cv_cpa');

  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { conv: 0, spend: 0 };
    plMap[pl].conv  += r.conversions;
    plMap[pl].spend += r.spend;
  });

  const sorted = Object.entries(plMap)
    .filter(([, d]) => d.conv > 0)
    .map(([pl, d]) => ({ pl, cpa: d.spend / d.conv }))
    .sort((a, b) => a.cpa - b.cpa); // ascending — cheaper first

  const canvas = el('ch_cv_cpa');
  if (!canvas) return;

  // Compute median CPA for coloring
  const cpas = sorted.map(d => d.cpa);
  const median = cpas[Math.floor(cpas.length / 2)] || 1;
  const colors = sorted.map(d =>
    d.cpa <= median * 0.8 ? alpha('#5ba33d', 0.82)
    : d.cpa <= median * 1.2 ? alpha('#c98a14', 0.82)
    : alpha('#c0392b', 0.82)
  );

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: sorted.map(d => d.pl),
      datasets: [{
        label: 'CPA (₫)',
        data: sorted.map(d => Math.round(d.cpa)),
        backgroundColor: colors,
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` CPA: ₫${Math.round(ctx.raw).toLocaleString('vi-VN')}`
          }
        }
      },
      scales: {
        x: {
          ticks: {
            font: { size: 10 },
            callback: v => v >= 1e6 ? '₫' + (v / 1e6).toFixed(1) + 'M' : '₫' + (v / 1e3).toFixed(0) + 'K'
          }
        },
        y: { ticks: { font: { size: 10 } }, grid: { display: false } }
      }
    }
  });
  registerChart('ch_cv_cpa', chart);

  const ic = el('ic_cv_cpa'), ins = el('ins_cv_cpa');
  if (ic && ins && sorted.length > 0) {
    const best  = sorted[0];
    const worst = sorted[sorted.length - 1];
    ic.className = 'insight-ic good'; ic.textContent = '✓';
    ins.innerHTML = `<b>${best.pl}</b> is most efficient at ₫${Math.round(best.cpa).toLocaleString('vi-VN')} CPA. `
      + `<b>${worst.pl}</b> costs ₫${Math.round(worst.cpa).toLocaleString('vi-VN')} per conversion — ${(worst.cpa / best.cpa).toFixed(1)}× more expensive.`;
  }
}

/* ── C2-b: Spend vs Conversions scatter by campaign ─────────────── */
export function drawSpendVsConvScatter(rows, utils) {
  const { alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_cv_scatter');

  const campMap = {};
  rows.forEach(r => {
    const camp = r.campaignId || 'Unknown';
    if (!campMap[camp]) campMap[camp] = { spend: 0, conv: 0, clk: 0, ch: r.channel || '' };
    campMap[camp].spend += r.spend;
    campMap[camp].conv  += r.conversions;
    campMap[camp].clk   += r.clicks;
  });

  const channels = [...new Set(Object.values(campMap).map(d => d.ch))];
  const datasets = channels.map((ch, i) => {
    const color = COLORS[i % COLORS.length];
    const pts = Object.entries(campMap)
      .filter(([, d]) => d.ch === ch && d.conv > 0)
      .map(([camp, d]) => ({
        x: +(d.spend / 1e6).toFixed(1), // spend in M₫
        y: d.conv,
        r: Math.max(6, Math.min(22, Math.sqrt(d.clk / 200))),
        label: camp
      }));
    return {
      label: ch,
      data: pts,
      backgroundColor: alpha(color, 0.72),
      borderColor: color,
      borderWidth: 1
    };
  });

  const canvas = el('ch_cv_scatter');
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
              return [`Campaign`, `Spend: ₫${pt.x}M`, `Conversions: ${pt.y}`];
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Total Spend (M₫)', font: { size: 10 } },
          ticks: { font: { size: 10 }, callback: v => '₫' + v + 'M' }
        },
        y: {
          title: { display: true, text: 'Conversions', font: { size: 10 } },
          ticks: { font: { size: 10 } }
        }
      }
    }
  });
  registerChart('ch_cv_scatter', chart);

  const ic = el('ic_cv_scatter'), ins = el('ins_cv_scatter');
  if (ic && ins) {
    ic.className = 'insight-ic'; ic.textContent = 'i';
    ins.innerHTML = `Each bubble = one campaign. <b>Upper-left</b> = high conversions at low spend (best CPA efficiency). Bubble size reflects click volume.`;
  }
}
