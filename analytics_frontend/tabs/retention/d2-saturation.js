/**
 * retention/d2-saturation.js
 * D2 — CTR Decay Curve (rolling 7-day avg vs baseline) + Audience Saturation Table
 * Use-case: Is creative fatigue setting in? Which placements are saturated?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── D2-a: CTR Decay Curve (rolling 7-day vs baseline) ─────────── */
export function drawCtrDecayCurve(rows, utils) {
  const { alpha, registerChart } = utils;
  destroyIfExists('ch_rt_decay');

  // Daily CTR
  const dateMap = {};
  rows.forEach(r => {
    if (!dateMap[r.date]) dateMap[r.date] = { imp: 0, clk: 0 };
    dateMap[r.date].imp += r.impressions;
    dateMap[r.date].clk += r.clicks;
  });

  const dates  = Object.keys(dateMap).sort();
  const dailyCTRs = dates.map(d =>
    dateMap[d].imp > 0 ? +(dateMap[d].clk / dateMap[d].imp * 100).toFixed(4) : 0
  );

  // Rolling 7-day average
  const rolling = dailyCTRs.map((_, i) => {
    const window = dailyCTRs.slice(Math.max(0, i - 6), i + 1);
    return +(window.reduce((s, v) => s + v, 0) / window.length).toFixed(4);
  });

  // Baseline = first 7-day average
  const baseline = rolling[Math.min(6, rolling.length - 1)];
  const baselineArr = new Array(dates.length).fill(+baseline.toFixed(4));

  const canvas = el('ch_rt_decay');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: dates.map(d => d.slice(5)),
      datasets: [
        {
          label: 'Daily CTR',
          data: dailyCTRs,
          borderColor: alpha('#2c7fb8', 0.5),
          backgroundColor: 'transparent',
          borderWidth: 1,
          pointRadius: 1.5,
          tension: 0.2,
          order: 3
        },
        {
          label: '7-day Rolling Avg',
          data: rolling,
          borderColor: '#1f3551',
          backgroundColor: alpha('#1f3551', 0.07),
          borderWidth: 2.5,
          pointRadius: 0,
          tension: 0.4,
          fill: true,
          order: 2
        },
        {
          label: 'Launch Baseline',
          data: baselineArr,
          borderColor: '#c98a14',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
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
            label: ctx => ` ${ctx.dataset.label}: ${ctx.raw.toFixed(3)}%`
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: { ticks: { font: { size: 10 }, callback: v => v.toFixed(2) + '%' } }
      }
    }
  });
  registerChart('ch_rt_decay', chart);

  const ic = el('ic_rt_decay'), ins = el('ins_rt_decay');
  if (ic && ins) {
    const lastRolling = rolling[rolling.length - 1];
    const decay = baseline > 0 ? (lastRolling - baseline) / baseline * 100 : 0;
    if (decay < -20) {
      ic.className = 'insight-ic bad'; ic.textContent = '▼';
      ins.innerHTML = `<b>Significant CTR decay: ${decay.toFixed(1)}%</b> from launch baseline of ${baseline.toFixed(3)}%. Current 7-day rolling: <b>${lastRolling.toFixed(3)}%</b>. Creative refresh strongly recommended.`;
    } else if (decay < -10) {
      ic.className = 'insight-ic warn'; ic.textContent = '⚠';
      ins.innerHTML = `<b>Mild CTR decay: ${decay.toFixed(1)}%</b> from baseline. Monitor closely — consider A/B testing a new creative variant.`;
    } else {
      ic.className = 'insight-ic good'; ic.textContent = '✓';
      ins.innerHTML = `CTR holding within <b>${Math.abs(decay).toFixed(1)}%</b> of launch baseline. No creative fatigue detected. Rolling avg: <b>${lastRolling.toFixed(3)}%</b>.`;
    }
  }
}

/* ── D2-b: Audience Saturation Table ────────────────────────────── */
export function renderSaturationTable(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = el('rt-saturation');
  if (!container) return;

  // Saturation score per placement: composite of freq, CTR decay, VI
  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { imp: 0, reach: 0, clk: 0, spend: 0, viSum: 0, n: 0,
      firstClk: 0, firstImp: 0, lastClk: 0, lastImp: 0 };
    const d = plMap[pl];
    d.imp   += r.impressions; d.reach += r.reach;
    d.clk   += r.clicks;      d.spend += r.spend;
    d.viSum += r.vi;          d.n++;
  });

  // For decay, group each placement's rows by date and compare first vs last 3rd
  const plDateMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plDateMap[pl]) plDateMap[pl] = {};
    if (!plDateMap[pl][r.date]) plDateMap[pl][r.date] = { imp: 0, clk: 0 };
    plDateMap[pl][r.date].imp += r.impressions;
    plDateMap[pl][r.date].clk += r.clicks;
  });

  const results = Object.entries(plMap).map(([pl, d]) => {
    const freq = d.reach > 0 ? d.imp / d.reach : 0;
    const ctr  = d.imp > 0 ? d.clk / d.imp * 100 : 0;
    const vi   = d.n > 0 ? d.viSum / d.n : 0;
    const cpc  = d.clk > 0 ? d.spend / d.clk : 0;

    // CTR decay within this placement
    const dates = Object.keys(plDateMap[pl] || {}).sort();
    const third = Math.max(1, Math.floor(dates.length / 3));
    const early = dates.slice(0, third);
    const late  = dates.slice(-third);
    const eImp = early.reduce((s, dt) => s + plDateMap[pl][dt].imp, 0);
    const eClk = early.reduce((s, dt) => s + plDateMap[pl][dt].clk, 0);
    const lImp = late.reduce((s, dt) => s + plDateMap[pl][dt].imp, 0);
    const lClk = late.reduce((s, dt) => s + plDateMap[pl][dt].clk, 0);
    const eCTR = eImp > 0 ? eClk / eImp * 100 : 0;
    const lCTR = lImp > 0 ? lClk / lImp * 100 : 0;
    const decay = eCTR > 0 ? (lCTR - eCTR) / eCTR * 100 : 0;

    // Saturation score 0–100: high freq + decay + low VI = saturated
    const freqScore  = Math.min(freq / 7 * 40, 40);
    const decayScore = Math.min(Math.abs(Math.min(decay, 0)) / 50 * 40, 40);
    const viScore    = Math.max(0, (70 - vi) / 70 * 20);
    const satScore   = Math.round(freqScore + decayScore + viScore);

    return { pl, freq, ctr, vi, decay, satScore, spend: d.spend, cpc };
  }).sort((a, b) => b.satScore - a.satScore);

  const pillSat = s => {
    const cls = s >= 70 ? 'bad' : s >= 40 ? 'watch' : 'good';
    const label = s >= 70 ? 'High' : s >= 40 ? 'Medium' : 'Low';
    return `<span class="pill ${cls}">${label} (${s})</span>`;
  };

  const pillDecay = d => {
    const cls = d <= -20 ? 'bad' : d <= -10 ? 'watch' : 'good';
    return `<span class="pill ${cls}">${d >= 0 ? '+' : ''}${d.toFixed(1)}%</span>`;
  };

  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>Placement</th>
            <th class="num">Avg Freq</th>
            <th class="num">CTR</th>
            <th class="num">CTR Decay</th>
            <th class="num">VI</th>
            <th class="num">Spend</th>
            <th class="num">CPC</th>
            <th class="num">Saturation Score ↓</th>
            <th class="num">Action</th>
          </tr>
        </thead>
        <tbody>
          ${results.map(r => `
            <tr>
              <td class="lab">${r.pl}</td>
              <td class="num">${r.freq.toFixed(1)}x</td>
              <td class="num">${r.ctr.toFixed(2)}%</td>
              <td class="num">${pillDecay(r.decay)}</td>
              <td class="num">${r.vi.toFixed(0)}%</td>
              <td class="num">${fmtVND(r.spend)}</td>
              <td class="num">${fmtVND(r.cpc)}</td>
              <td class="num">${pillSat(r.satScore)}</td>
              <td class="num" style="font-size:11px;color:var(--muted)">
                ${r.satScore >= 70 ? '⛔ Pause / Refresh' : r.satScore >= 40 ? '⚠ Monitor' : '✔ Scale'}
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  const ic = el('ic_rt_sat'), ins = el('ins_rt_sat');
  if (ic && ins && results.length > 0) {
    const highSat = results.filter(r => r.satScore >= 70);
    ic.className = highSat.length > 0 ? 'insight-ic bad' : 'insight-ic good';
    ic.textContent = highSat.length > 0 ? '⚠' : '✓';
    ins.innerHTML = highSat.length > 0
      ? `<b>${highSat.length}</b> placement${highSat.length > 1 ? 's' : ''} are highly saturated: <b>${highSat.map(r => r.pl).join(', ')}</b>. Pause or rotate creative to recover performance.`
      : `No placements in high saturation zone. Continue monitoring weekly. Score combines frequency, CTR decay, and viewability.`;
  }
}
