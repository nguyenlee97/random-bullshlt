/**
 * awareness/a1-reach.js
 * A1 — Daily Reach Trend + Frequency Distribution + CPM Trend
 * Use-case: Are we hitting new people each day?
 * Decision rule: reach% drops but impressions stay flat → over-frequency
 *                frequency > 5 → cap/suppress that segment
 */

/* ── local helpers ─────────────────────────────────────────────── */
function el(id) { return document.getElementById(id); }

function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

function fmtK(v) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
  if (v >= 1_000)     return (v / 1_000).toFixed(0) + 'K';
  return String(Math.round(v));
}

/* ── A1-a: Daily Reach + Frequency dual-axis line chart ─────────── */
export function drawReachTrend(rows, utils) {
  const { fmt, alpha, registerChart } = utils;
  destroyIfExists('ch_aw_reach');

  // Group by date
  const dateMap = {};
  rows.forEach(r => {
    if (!dateMap[r.date]) dateMap[r.date] = { imp: 0, reach: 0 };
    dateMap[r.date].imp   += r.impressions;
    dateMap[r.date].reach += r.reach;
  });

  const dates = Object.keys(dateMap).sort();
  const reaches = dates.map(d => dateMap[d].reach);
  const freqs   = dates.map(d => {
    const { imp, reach } = dateMap[d];
    return reach > 0 ? +(imp / reach).toFixed(2) : 0;
  });

  const canvas = el('ch_aw_reach');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    data: {
      labels: dates.map(d => d.slice(5)),
      datasets: [
        {
          type: 'bar',
          label: 'Daily Reach',
          data: reaches,
          backgroundColor: alpha('#2c7fb8', 0.7),
          yAxisID: 'y',
          order: 2
        },
        {
          type: 'line',
          label: 'Frequency',
          data: freqs,
          borderColor: '#c98a14',
          backgroundColor: alpha('#c98a14', 0.08),
          borderWidth: 2.5,
          pointRadius: 3,
          fill: false,
          tension: 0.3,
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
            label: ctx => ctx.dataset.label === 'Frequency'
              ? ` Freq: ${ctx.raw}x`
              : ` Reach: ${fmt(ctx.raw)}`
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: {
          type: 'linear', position: 'left',
          title: { display: true, text: 'Reach', font: { size: 10 } },
          ticks: { font: { size: 10 }, callback: v => fmtK(v) }
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

  registerChart('ch_aw_reach', chart);
  _updateReachInsight(dates, reaches, freqs, fmt);
}

function _updateReachInsight(dates, reaches, freqs, fmt) {
  const ic  = el('ic_aw_reach');
  const ins = el('ins_aw_reach');
  if (!ic || !ins) return;

  const avgFreq = freqs.reduce((s, v) => s + v, 0) / (freqs.length || 1);
  const maxFreq = Math.max(...freqs);
  const peakDate = dates[freqs.indexOf(maxFreq)];
  const totReach = reaches.reduce((s, v) => s + v, 0);

  if (maxFreq > 5) {
    ic.className = 'insight-ic bad'; ic.textContent = '⚠';
    ins.innerHTML = `<b>Over-frequency detected</b> — peak ${maxFreq.toFixed(1)}x on <b>${peakDate}</b>. Avg: <b>${avgFreq.toFixed(1)}x</b>. Consider adding frequency caps to prevent ad fatigue.`;
  } else if (avgFreq > 3) {
    ic.className = 'insight-ic warn'; ic.textContent = '⚠';
    ins.innerHTML = `<b>Moderate frequency</b> — avg <b>${avgFreq.toFixed(1)}x</b>. Cumulative unique reach: <b>${fmt(totReach)}</b>. Monitor weekly to prevent saturation.`;
  } else {
    ic.className = 'insight-ic good'; ic.textContent = '✓';
    ins.innerHTML = `<b>Healthy frequency</b> — avg <b>${avgFreq.toFixed(1)}x</b>, well within the ≤3 benchmark. Cumulative unique reach: <b>${fmt(totReach)}</b>.`;
  }
}

/* ── A1-b: CPM Trend line with benchmark annotation ─────────────── */
export function drawCpmTrend(rows, utils) {
  const { alpha, registerChart } = utils;
  destroyIfExists('ch_aw_cpm');

  const dateMap = {};
  rows.forEach(r => {
    if (!dateMap[r.date]) dateMap[r.date] = { cpmSum: 0, n: 0 };
    dateMap[r.date].cpmSum += r.cpm;
    dateMap[r.date].n++;
  });

  const dates  = Object.keys(dateMap).sort();
  const cpms   = dates.map(d => +(dateMap[d].cpmSum / dateMap[d].n).toFixed(0));
  const avgCPM = cpms.reduce((s, v) => s + v, 0) / (cpms.length || 1);
  const bench  = new Array(dates.length).fill(Math.round(avgCPM));

  const canvas = el('ch_aw_cpm');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: dates.map(d => d.slice(5)),
      datasets: [
        {
          label: 'Daily Avg CPM (₫)',
          data: cpms,
          borderColor: '#1f3551',
          backgroundColor: alpha('#1f3551', 0.08),
          borderWidth: 2.5,
          pointRadius: 3,
          tension: 0.3,
          fill: true,
          order: 1
        },
        {
          label: 'Period Avg',
          data: bench,
          borderColor: '#c98a14',
          borderDash: [5, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          order: 2
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
            label: ctx => ` ${ctx.dataset.label}: ₫${Math.round(ctx.raw).toLocaleString('vi-VN')}`
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: { ticks: { font: { size: 10 }, callback: v => '₫' + fmtK(v) } }
      }
    }
  });

  registerChart('ch_aw_cpm', chart);

  // Insight
  const ic  = el('ic_aw_cpm');
  const ins = el('ins_aw_cpm');
  if (ic && ins) {
    const last3Avg = cpms.slice(-3).reduce((s, v) => s + v, 0) / 3;
    if (last3Avg > avgCPM * 1.15) {
      ic.className = 'insight-ic bad'; ic.textContent = '▲';
      ins.innerHTML = `<b>CPM rising</b> — last 3-day avg ₫${Math.round(last3Avg).toLocaleString('vi-VN')} vs period avg ₫${Math.round(avgCPM).toLocaleString('vi-VN')}. Increased competition or audience saturation may be driving costs up.`;
    } else if (last3Avg < avgCPM * 0.85) {
      ic.className = 'insight-ic good'; ic.textContent = '▼';
      ins.innerHTML = `<b>CPM improving</b> — last 3-day avg ₫${Math.round(last3Avg).toLocaleString('vi-VN')}, below period avg. Buying efficiency is increasing.`;
    } else {
      ic.className = 'insight-ic'; ic.textContent = 'i';
      ins.innerHTML = `CPM stable around ₫${Math.round(avgCPM).toLocaleString('vi-VN')} across the period.`;
    }
  }
}

/* ── A1-c: Frequency distribution bar chart ─────────────────────── */
export function drawFreqDistribution(rows, utils) {
  const { alpha, registerChart } = utils;
  destroyIfExists('ch_aw_freq');

  // Compute per-date frequency, then bin
  const dateMap = {};
  rows.forEach(r => {
    if (!dateMap[r.date]) dateMap[r.date] = { imp: 0, reach: 0 };
    dateMap[r.date].imp   += r.impressions;
    dateMap[r.date].reach += r.reach;
  });

  const bins = { '<2': 0, '2–3': 0, '3–5': 0, '5–7': 0, '7+': 0 };
  Object.values(dateMap).forEach(({ imp, reach }) => {
    if (!reach) return;
    const f = imp / reach;
    if (f < 2)      bins['<2']++;
    else if (f < 3) bins['2–3']++;
    else if (f < 5) bins['3–5']++;
    else if (f < 7) bins['5–7']++;
    else            bins['7+']++;
  });

  const labels = Object.keys(bins);
  const vals   = Object.values(bins);
  const colors = ['#5ba33d', '#27ae60', '#c98a14', '#e67e22', '#c0392b'];

  const canvas = el('ch_aw_freq');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Days in frequency band',
        data: vals,
        backgroundColor: colors.map(c => alpha(c, 0.8)),
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.raw} days at this frequency` } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11 } } },
        y: { ticks: { font: { size: 10 }, stepSize: 1 } }
      }
    }
  });

  registerChart('ch_aw_freq', chart);

  const ic  = el('ic_aw_freq');
  const ins = el('ins_aw_freq');
  if (ic && ins) {
    const highFreqDays = (bins['5–7'] || 0) + (bins['7+'] || 0);
    const totalDays = Object.values(bins).reduce((s, v) => s + v, 0) || 1;
    ic.className = highFreqDays / totalDays > 0.3 ? 'insight-ic bad' : 'insight-ic good';
    ic.textContent = highFreqDays / totalDays > 0.3 ? '⚠' : '✓';
    ins.innerHTML = `<b>${highFreqDays}</b> of <b>${totalDays}</b> days had frequency ≥5 (over-exposure risk zone). <b>${bins['<2'] + bins['2–3']}</b> days were in the healthy &lt;3x range.`;
  }
}
