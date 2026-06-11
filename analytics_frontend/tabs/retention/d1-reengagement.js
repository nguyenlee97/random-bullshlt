/**
 * retention/d1-reengagement.js
 * D1 — Week-over-Week Reach (grouped bar) + Frequency by Placement (horizontal bar)
 * Use-case: Is the campaign reaching new audiences each week or re-hitting the same users?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── D1-a: Week-over-Week Reach grouped bar ─────────────────────── */
export function drawWoWReach(rows, utils) {
  const { fmt, alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_rt_wow');

  // Group by ISO week
  const weekMap = {};
  rows.forEach(r => {
    if (!r.date) return;
    const d = new Date(r.date);
    const jan1 = new Date(d.getFullYear(), 0, 1);
    const week = Math.ceil(((d - jan1) / 86400000 + jan1.getDay() + 1) / 7);
    const wk = `W${String(week).padStart(2, '0')}`;
    if (!weekMap[wk]) weekMap[wk] = { reach: 0, imp: 0, clk: 0 };
    weekMap[wk].reach += r.reach;
    weekMap[wk].imp   += r.impressions;
    weekMap[wk].clk   += r.clicks;
  });

  const weeks  = Object.keys(weekMap).sort();
  const reaches = weeks.map(w => weekMap[w].reach);
  const imps    = weeks.map(w => weekMap[w].imp);
  const freqs   = weeks.map((w, i) => reaches[i] > 0 ? +(imps[i] / reaches[i]).toFixed(2) : 0);

  const canvas = el('ch_rt_wow');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    data: {
      labels: weeks,
      datasets: [
        {
          type: 'bar',
          label: 'Weekly Reach',
          data: reaches,
          backgroundColor: alpha('#2c7fb8', 0.78),
          yAxisID: 'y',
          order: 2
        },
        {
          type: 'line',
          label: 'Avg Frequency',
          data: freqs,
          borderColor: '#c98a14',
          backgroundColor: alpha('#c98a14', 0.1),
          borderWidth: 2.5,
          pointRadius: 4,
          tension: 0.3,
          fill: false,
          yAxisID: 'y2',
          order: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
        tooltip: {
          callbacks: {
            label: ctx => ctx.dataset.label === 'Avg Frequency'
              ? ` Freq: ${ctx.raw}x`
              : ` Reach: ${fmt(ctx.raw)}`
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 12 } } },
        y: {
          type: 'linear', position: 'left',
          title: { display: true, text: 'Reach', font: { size: 10 } },
          ticks: {
            font: { size: 10 },
            callback: v => v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(0) + 'K' : v
          }
        },
        y2: {
          type: 'linear', position: 'right',
          title: { display: true, text: 'Frequency', font: { size: 10 } },
          grid: { drawOnChartArea: false },
          ticks: { font: { size: 10 }, callback: v => v.toFixed(1) + 'x' },
          suggestedMin: 0, suggestedMax: 8
        }
      }
    }
  });
  registerChart('ch_rt_wow', chart);

  const ic = el('ic_rt_wow'), ins = el('ins_rt_wow');
  if (ic && ins && weeks.length >= 2) {
    const lastReach  = reaches[reaches.length - 1];
    const priorReach = reaches[reaches.length - 2] || 1;
    const pct = ((lastReach - priorReach) / priorReach * 100).toFixed(1);
    const lastFreq = freqs[freqs.length - 1];
    ic.className = lastReach > priorReach ? 'insight-ic good' : 'insight-ic warn';
    ic.textContent = lastReach > priorReach ? '▲' : '▼';
    ins.innerHTML = `Last week reach <b>${pct >= 0 ? '+' : ''}${pct}%</b> vs prior week. `
      + `Current week frequency: <b>${lastFreq}x</b>`
      + (lastFreq > 5 ? ' — <b style="color:#c0392b">over-frequency detected</b>, add frequency cap.' : ' — within healthy range.');
  }
}

/* ── D1-b: Frequency Distribution by Placement (horizontal grouped) */
export function drawFreqByPlacement(rows, utils) {
  const { alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_rt_freq_pl');

  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { imp: 0, reach: 0 };
    plMap[pl].imp   += r.impressions;
    plMap[pl].reach += r.reach;
  });

  const sorted = Object.entries(plMap)
    .filter(([, d]) => d.reach > 0)
    .map(([pl, d]) => ({ pl, freq: +(d.imp / d.reach).toFixed(2) }))
    .sort((a, b) => b.freq - a.freq);

  const canvas = el('ch_rt_freq_pl');
  if (!canvas) return;

  const colors = sorted.map(d =>
    d.freq > 5 ? alpha('#c0392b', 0.82)
    : d.freq > 3 ? alpha('#c98a14', 0.82)
    : alpha('#5ba33d', 0.82)
  );

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: sorted.map(d => d.pl),
      datasets: [{
        label: 'Avg Frequency',
        data: sorted.map(d => d.freq),
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
        tooltip: { callbacks: { label: ctx => ` Frequency: ${ctx.raw}x` } }
      },
      scales: {
        x: {
          ticks: { font: { size: 10 }, callback: v => v + 'x' },
          grid: { color: 'rgba(0,0,0,.04)' }
        },
        y: { ticks: { font: { size: 10 } }, grid: { display: false } }
      }
    }
  });
  registerChart('ch_rt_freq_pl', chart);

  const ic = el('ic_rt_freq_pl'), ins = el('ins_rt_freq_pl');
  if (ic && ins && sorted.length > 0) {
    const over = sorted.filter(d => d.freq > 5);
    ic.className = over.length > 0 ? 'insight-ic bad' : 'insight-ic good';
    ic.textContent = over.length > 0 ? '⚠' : '✓';
    ins.innerHTML = over.length > 0
      ? `<b>${over.length}</b> placement${over.length > 1 ? 's' : ''} exceed 5x frequency cap: <b>${over.map(d => d.pl).join(', ')}</b>. Immediate frequency capping recommended.`
      : `All placements within healthy frequency range (&lt;5x). Best: <b>${sorted[sorted.length - 1].pl}</b> at ${sorted[sorted.length - 1].freq}x.`;
  }
}
