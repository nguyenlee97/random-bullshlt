/**
 * conversion/c1-conv-trend.js
 * C1 — Daily Conversions (bars) + CVR % trend (line), dual axis
 * Use-case: Is conversion volume growing? Is click-to-conversion rate holding?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── C1-a: Daily Conversions + CVR dual-axis combo ──────────────── */
export function drawConversionTrend(rows, utils) {
  const { fmt, alpha, registerChart } = utils;
  destroyIfExists('ch_cv_trend');

  const dateMap = {};
  rows.forEach(r => {
    if (!dateMap[r.date]) dateMap[r.date] = { conv: 0, clk: 0, imp: 0 };
    dateMap[r.date].conv += r.conversions;
    dateMap[r.date].clk  += r.clicks;
    dateMap[r.date].imp  += r.impressions;
  });

  const dates = Object.keys(dateMap).sort();
  const convs = dates.map(d => dateMap[d].conv);
  const cvrs  = dates.map(d => {
    const { conv, clk } = dateMap[d];
    return clk > 0 ? +(conv / clk * 100).toFixed(3) : 0;
  });

  const canvas = el('ch_cv_trend');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    data: {
      labels: dates.map(d => d.slice(5)),
      datasets: [
        {
          type: 'bar',
          label: 'Conversions',
          data: convs,
          backgroundColor: alpha('#5ba33d', 0.78),
          yAxisID: 'y',
          order: 2
        },
        {
          type: 'line',
          label: 'CVR %',
          data: cvrs,
          borderColor: '#c98a14',
          backgroundColor: alpha('#c98a14', 0.1),
          borderWidth: 2.5,
          pointRadius: 3,
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
            label: ctx => ctx.dataset.label === 'CVR %'
              ? ` CVR: ${ctx.raw.toFixed(2)}%`
              : ` Conversions: ${fmt(ctx.raw)}`
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: {
          type: 'linear', position: 'left',
          title: { display: true, text: 'Conversions', font: { size: 10 } },
          ticks: { font: { size: 10 } }
        },
        y2: {
          type: 'linear', position: 'right',
          title: { display: true, text: 'CVR %', font: { size: 10 } },
          grid: { drawOnChartArea: false },
          ticks: { font: { size: 10 }, callback: v => v.toFixed(2) + '%' }
        }
      }
    }
  });
  registerChart('ch_cv_trend', chart);

  // Insight
  const ic = el('ic_cv_trend'), ins = el('ins_cv_trend');
  if (ic && ins) {
    const mid = Math.floor(dates.length / 2);
    const firstAvg = cvrs.slice(0, mid).reduce((s, v) => s + v, 0) / Math.max(mid, 1);
    const lastAvg  = cvrs.slice(mid).reduce((s, v) => s + v, 0) / Math.max(dates.length - mid, 1);
    const totConv  = convs.reduce((s, v) => s + v, 0);
    if (lastAvg > firstAvg * 1.1) {
      ic.className = 'insight-ic good'; ic.textContent = '▲';
      ins.innerHTML = `<b>CVR improving</b> — second-half avg ${lastAvg.toFixed(2)}% vs ${firstAvg.toFixed(2)}%. Total <b>${fmt(totConv)}</b> conversions.`;
    } else if (lastAvg < firstAvg * 0.9) {
      ic.className = 'insight-ic bad'; ic.textContent = '▼';
      ins.innerHTML = `<b>CVR declining</b> — second-half avg ${lastAvg.toFixed(2)}% vs ${firstAvg.toFixed(2)}%. Investigate landing page or offer quality.`;
    } else {
      ic.className = 'insight-ic'; ic.textContent = 'i';
      ins.innerHTML = `CVR stable around <b>${lastAvg.toFixed(2)}%</b>. Total <b>${fmt(totConv)}</b> conversions across <b>${dates.length}</b> days.`;
    }
  }
}

/* ── C1-b: CVR by Channel — horizontal bar ──────────────────────── */
export function drawCvrByChannel(rows, utils) {
  const { alpha, registerChart } = utils;
  destroyIfExists('ch_cv_cvr_ch');

  const chMap = {};
  rows.forEach(r => {
    const ch = r.channel || 'Unknown';
    if (!chMap[ch]) chMap[ch] = { conv: 0, clk: 0 };
    chMap[ch].conv += r.conversions;
    chMap[ch].clk  += r.clicks;
  });

  const sorted = Object.entries(chMap)
    .filter(([, d]) => d.clk > 0)
    .map(([ch, d]) => ({ ch, cvr: +(d.conv / d.clk * 100).toFixed(3) }))
    .sort((a, b) => b.cvr - a.cvr);

  const canvas = el('ch_cv_cvr_ch');
  if (!canvas) return;

  const colors = sorted.map(d =>
    d.cvr >= 5 ? alpha('#5ba33d', 0.82) : d.cvr >= 2 ? alpha('#c98a14', 0.82) : alpha('#c0392b', 0.82)
  );

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: sorted.map(d => d.ch),
      datasets: [{
        label: 'CVR %',
        data: sorted.map(d => d.cvr),
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
        tooltip: { callbacks: { label: ctx => ` CVR: ${ctx.raw.toFixed(2)}%` } }
      },
      scales: {
        x: { ticks: { font: { size: 10 }, callback: v => v.toFixed(1) + '%' } },
        y: { ticks: { font: { size: 11 } }, grid: { display: false } }
      }
    }
  });
  registerChart('ch_cv_cvr_ch', chart);

  const ic = el('ic_cv_cvr_ch'), ins = el('ins_cv_cvr_ch');
  if (ic && ins && sorted.length > 0) {
    const best = sorted[0];
    ic.className = 'insight-ic good'; ic.textContent = '✓';
    ins.innerHTML = `<b>${best.ch}</b> has the highest CVR at <b>${best.cvr.toFixed(2)}%</b>. Scale this channel for conversion-focused objectives.`;
  }
}
