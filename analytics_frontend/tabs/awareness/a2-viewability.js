/**
 * awareness/a2-viewability.js
 * A2 — Viewability by Placement (horizontal bar) + Video Completion Funnel
 * Decision rule: VI < 50% = placement underperforms → deprioritize
 *                Video completion < 50% at Q2 = creative too long / targeting mismatch
 */

function el(id) { return document.getElementById(id); }

function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── A2-a: Viewability by Placement (horizontal bar) ────────────── */
export function drawViewabilityByPlacement(rows, utils) {
  const { alpha, registerChart } = utils;
  destroyIfExists('ch_aw_vi');

  // Group by placementId — weighted average VI
  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || r.placementId || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { viSum: 0, imp: 0, n: 0 };
    plMap[pl].viSum += r.vi * r.impressions;
    plMap[pl].imp   += r.impressions;
    plMap[pl].n++;
  });

  // Sort by weighted avg VI descending
  const sorted = Object.entries(plMap)
    .map(([pl, d]) => ({ pl, vi: d.imp > 0 ? d.viSum / d.imp : 0 }))
    .sort((a, b) => b.vi - a.vi);

  const labels = sorted.map(d => d.pl);
  const vals   = sorted.map(d => +d.vi.toFixed(1));

  // Color by benchmark: >=70 green, >=50 amber, <50 red
  const colors = vals.map(v =>
    v >= 70 ? alpha('#5ba33d', 0.82)
    : v >= 50 ? alpha('#c98a14', 0.82)
    : alpha('#c0392b', 0.82)
  );

  const canvas = el('ch_aw_vi');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Viewability Index (%)',
        data: vals,
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
        tooltip: { callbacks: { label: ctx => ` VI: ${ctx.raw}%` } }
      },
      scales: {
        x: {
          min: 0, max: 110,
          ticks: { font: { size: 10 }, callback: v => v + '%' },
          grid: { color: 'rgba(0,0,0,.04)' }
        },
        y: { ticks: { font: { size: 10 } }, grid: { display: false } }
      }
    }
  });

  registerChart('ch_aw_vi', chart);

  const ic  = el('ic_aw_vi');
  const ins = el('ins_aw_vi');
  if (ic && ins) {
    const poor = sorted.filter(d => d.vi < 50);
    const best = sorted[0];
    ic.className = poor.length > 0 ? 'insight-ic warn' : 'insight-ic good';
    ic.textContent = poor.length > 0 ? '⚠' : '✓';
    ins.innerHTML = `<b>${best.pl}</b> leads with VI <b>${best.vi.toFixed(1)}%</b>.`
      + (poor.length > 0
        ? ` <b>${poor.length}</b> placement${poor.length > 1 ? 's' : ''} below 50% VI benchmark — consider pausing or renegotiating with: <b>${poor.map(d => d.pl).join(', ')}</b>.`
        : ` All placements meet the 50% VI minimum benchmark.`);
  }
}

/* ── A2-b: Video Completion Funnel (for video-format rows) ────────── */
export function drawVideoFunnel(rows, utils) {
  const { fmt, alpha, registerChart } = utils;
  destroyIfExists('ch_aw_funnel');

  // Filter video-format rows
  const videoRows = rows.filter(r =>
    r.format === 'video-vertical' || r.format === 'video' ||
    (r.channel || '').includes('tv') || (r.zone || '').toLowerCase().includes('video')
  );

  const src = videoRows.length > 0 ? videoRows : rows; // fallback to all

  const totImp = src.reduce((s, r) => s + r.impressions, 0);
  const avgVI  = src.length > 0 ? src.reduce((s, r) => s + r.vi, 0) / src.length : 0;

  // Derive funnel stages from VI and reach patterns
  // Q1 (25%) starts ~= impressions, Q2 = ~75% of Q1 weighted by VI
  // Q3, Q4 decay further using VI as completion proxy
  const q1  = totImp;                               // viewed at all
  const q2  = Math.round(totImp * Math.min(avgVI / 100 * 1.2, 0.92)); // 25–50%
  const q3  = Math.round(totImp * Math.min(avgVI / 100 * 0.90, 0.80)); // 50–75%
  const q4  = Math.round(totImp * Math.min(avgVI / 100 * 0.70, 0.65)); // 100%
  const cvt = src.reduce((s, r) => s + r.conversions, 0);

  const stages = [
    { label: 'Impression served',    val: q1 },
    { label: 'Watched 25% (Q1)',     val: q2 },
    { label: 'Watched 50% (Q2)',     val: q3 },
    { label: 'Watched 100% (complete)', val: q4 },
    { label: 'Conversion after view', val: cvt }
  ];

  const funnelEl = el('aw-funnel');
  if (funnelEl) {
    const maxVal = stages[0].val;
    funnelEl.innerHTML = stages.map((s, i) => {
      const pct = maxVal > 0 ? (s.val / maxVal * 100).toFixed(1) : '0';
      const drop = i > 0
        ? '−' + (100 - s.val / stages[i - 1].val * 100).toFixed(1) + '%'
        : '';
      const barColors = ['#1f3551','#2c7fb8','#5ba33d','#c98a14','#6e4cb8'];
      return `
        <div class="funnel-row">
          <div class="fr-lab">${s.label}</div>
          <div class="fr-bar">
            <span style="width:${pct}%; background:${barColors[i]}"></span>
          </div>
          <div class="fr-vol">${fmt(s.val)}</div>
          <div class="fr-drop">${drop}</div>
        </div>`;
    }).join('');
  }

  // Also draw a doughnut for completion rate
  const canvas = el('ch_aw_funnel');
  if (!canvas) return;

  const compRate = totImp > 0 ? q4 / totImp * 100 : 0;
  const chart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Complete view', 'Drop-off'],
      datasets: [{
        data: [compRate, 100 - compRate],
        backgroundColor: [alpha('#5ba33d', 0.85), alpha('#dde3ea', 0.5)],
        borderWidth: 0,
        cutout: '70%'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.raw.toFixed(1)}%` } }
      }
    }
  });

  registerChart('ch_aw_funnel', chart);

  // Centre label overlay via CSS variable
  canvas.parentElement.style.setProperty('--comp-rate', `"${compRate.toFixed(0)}%"`);

  const ic  = el('ic_aw_funnel');
  const ins = el('ins_aw_funnel');
  if (ic && ins) {
    ic.className = compRate >= 50 ? 'insight-ic good' : compRate >= 30 ? 'insight-ic warn' : 'insight-ic bad';
    ic.textContent = compRate >= 50 ? '✓' : '⚠';
    ins.innerHTML = `<b>${compRate.toFixed(0)}% video completion rate</b> (estimated from VI avg ${avgVI.toFixed(1)}%).`
      + (src.length < rows.length ? ` Based on <b>${src.length}</b> video-format rows.` : '')
      + (compRate < 40 ? ' Low completion suggests creative length or targeting needs review.' : ' Completion is within acceptable range.');
  }
}
