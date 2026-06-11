/**
 * executive/e2-budget.js
 * E2 — Spend Pacing Line + Channel Spend Allocation Donut
 * Use-case: Is spend pacing correctly? Where is budget going?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── E2-a: Cumulative Spend Pacing vs Linear Budget ─────────────── */
export function drawSpendPacing(rows, utils) {
  const { alpha, registerChart } = utils;
  destroyIfExists('ch_ex_pacing');

  const dateMap = {};
  rows.forEach(r => { dateMap[r.date] = (dateMap[r.date] || 0) + r.spend; });
  const dates = Object.keys(dateMap).sort();
  const dailySpends = dates.map(d => dateMap[d]);

  // Cumulative actual
  const cumActual = dailySpends.reduce((acc, v) => {
    acc.push((acc[acc.length - 1] || 0) + v);
    return acc;
  }, []);

  const totalSpend = cumActual[cumActual.length - 1] || 0;

  // Ideal linear pacing
  const cumIdeal = dates.map((_, i) => totalSpend * (i + 1) / dates.length);

  const canvas = el('ch_ex_pacing');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: dates.map(d => d.slice(5)),
      datasets: [
        {
          label: 'Actual Cumulative Spend',
          data: cumActual,
          borderColor: '#1f3551',
          backgroundColor: alpha('#1f3551', 0.08),
          borderWidth: 2.5,
          fill: true,
          tension: 0.2,
          pointRadius: 1.5
        },
        {
          label: 'Ideal Linear Pacing',
          data: cumIdeal,
          borderColor: '#c98a14',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false
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
            label: ctx => {
              const v = ctx.raw;
              const s = v >= 1e9 ? '₫' + (v / 1e9).toFixed(2) + 'B'
                : v >= 1e6 ? '₫' + (v / 1e6).toFixed(1) + 'M'
                : '₫' + Math.round(v).toLocaleString('vi-VN');
              return ` ${ctx.dataset.label}: ${s}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: {
          ticks: {
            font: { size: 10 },
            callback: v => v >= 1e9 ? '₫' + (v / 1e9).toFixed(1) + 'B'
              : v >= 1e6 ? '₫' + (v / 1e6).toFixed(0) + 'M' : v
          }
        }
      }
    }
  });
  registerChart('ch_ex_pacing', chart);

  // Pacing insight
  const ic = el('ic_ex_pacing'), ins = el('ins_ex_pacing');
  if (ic && ins && dates.length > 1) {
    const midIdx   = Math.floor(dates.length / 2);
    const actualMid = cumActual[midIdx];
    const idealMid  = cumIdeal[midIdx];
    const deviation = idealMid > 0 ? (actualMid - idealMid) / idealMid * 100 : 0;
    if (deviation > 15) {
      ic.className = 'insight-ic warn'; ic.textContent = '▲';
      ins.innerHTML = `<b>Front-loaded spend</b> — ${deviation.toFixed(1)}% ahead of linear pacing at mid-period. Monitor for budget exhaustion before campaign end.`;
    } else if (deviation < -15) {
      ic.className = 'insight-ic warn'; ic.textContent = '▼';
      ins.innerHTML = `<b>Under-pacing</b> — ${Math.abs(deviation).toFixed(1)}% behind ideal at mid-period. Risk of under-delivery. Consider increasing bids or broadening targeting.`;
    } else {
      ic.className = 'insight-ic good'; ic.textContent = '✓';
      ins.innerHTML = `Spend pacing on track — within <b>${Math.abs(deviation).toFixed(1)}%</b> of ideal at mid-period. Total spend: <b>₫${(totalSpend / 1e9).toFixed(2)}B</b>.`;
    }
  }
}

/* ── E2-b: Channel Spend Allocation Donut ────────────────────────── */
export function drawChannelAllocation(rows, utils) {
  const { alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_ex_donut');

  const chMap = {};
  rows.forEach(r => { chMap[r.channel] = (chMap[r.channel] || 0) + r.spend; });
  const sorted = Object.entries(chMap).sort((a, b) => b[1] - a[1]);
  const labels = sorted.map(e => e[0]);
  const vals   = sorted.map(e => e[1]);
  const total  = vals.reduce((s, v) => s + v, 0);

  const canvas = el('ch_ex_donut');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: vals,
        backgroundColor: COLORS.slice(0, labels.length).map(c => alpha(c, 0.85)),
        borderWidth: 2,
        borderColor: '#fff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { font: { size: 11 }, boxWidth: 14 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const pct = (ctx.raw / total * 100).toFixed(1);
              const v = ctx.raw >= 1e9 ? '₫' + (ctx.raw / 1e9).toFixed(2) + 'B'
                : ctx.raw >= 1e6 ? '₫' + (ctx.raw / 1e6).toFixed(1) + 'M'
                : '₫' + Math.round(ctx.raw).toLocaleString('vi-VN');
              return ` ${ctx.label}: ${v} (${pct}%)`;
            }
          }
        }
      }
    }
  });
  registerChart('ch_ex_donut', chart);

  const ic = el('ic_ex_donut'), ins = el('ins_ex_donut');
  if (ic && ins && sorted.length > 0) {
    const top = sorted[0];
    const pct = total > 0 ? (top[1] / total * 100).toFixed(1) : 0;
    ic.className = parseFloat(pct) > 60 ? 'insight-ic warn' : 'insight-ic good';
    ic.textContent = parseFloat(pct) > 60 ? '⚠' : 'i';
    ins.innerHTML = `<b>${top[0]}</b> accounts for <b>${pct}%</b> of total spend.`
      + (parseFloat(pct) > 60 ? ' High channel concentration — consider diversifying to reduce dependency risk.' : ` Budget is distributed across <b>${labels.length}</b> channels.`);
  }
}
