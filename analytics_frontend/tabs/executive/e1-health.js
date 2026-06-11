/**
 * executive/e1-health.js
 * E1 — Campaign Health Traffic-Light Table + Radar Chart
 * Scores each campaign across 5 dimensions: CTR, CVR, VI, Frequency, Spend Efficiency
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

// Score each metric 0–100
function scoreCTR(v)   { return Math.min(v / 1.0 * 100, 100); }   // 1% CTR = 100
function scoreCVR(v)   { return Math.min(v / 8.0 * 100, 100); }   // 8% CVR = 100
function scoreVI(v)    { return Math.min(v / 80 * 100, 100); }    // 80% VI = 100
function scoreFreq(v)  { return Math.max(0, 100 - (v - 1) / 6 * 100); } // freq 1=100, 7=0
function scoreCPA(cpa, avgCpa) {
  if (!avgCpa) return 50;
  const ratio = cpa / avgCpa;
  return Math.max(0, Math.min(100, 100 - (ratio - 1) * 80));
}

/* ── E1-a: Campaign Health Table ────────────────────────────────── */
export function renderHealthTable(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = el('ex-health-table');
  if (!container) return;

  const campMap = {};
  rows.forEach(r => {
    const c = r.campaignId || 'Unknown';
    if (!campMap[c]) campMap[c] = { imp: 0, reach: 0, clk: 0, conv: 0, spend: 0, vi: 0, n: 0 };
    campMap[c].imp   += r.impressions;
    campMap[c].reach += r.reach;
    campMap[c].clk   += r.clicks;
    campMap[c].conv  += r.conversions;
    campMap[c].spend += r.spend;
    campMap[c].vi    += r.vi;
    campMap[c].n++;
  });

  const avgCpa = (() => {
    const total = Object.values(campMap);
    const conv  = total.reduce((s, d) => s + d.conv, 0);
    const spend = total.reduce((s, d) => s + d.spend, 0);
    return conv > 0 ? spend / conv : 0;
  })();

  const campaigns = Object.entries(campMap).map(([camp, d]) => {
    const ctr  = d.imp   > 0 ? d.clk  / d.imp   * 100 : 0;
    const cvr  = d.clk   > 0 ? d.conv / d.clk   * 100 : 0;
    const vi   = d.n     > 0 ? d.vi   / d.n          : 0;
    const freq = d.reach > 0 ? d.imp  / d.reach       : 0;
    const cpa  = d.conv  > 0 ? d.spend / d.conv       : 0;

    const scores = {
      ctr:  scoreCTR(ctr),
      cvr:  scoreCVR(cvr),
      vi:   scoreVI(vi),
      freq: scoreFreq(freq),
      eff:  scoreCPA(cpa, avgCpa)
    };
    const overall = Object.values(scores).reduce((s, v) => s + v, 0) / 5;

    return { camp, ctr, cvr, vi, freq, cpa, spend: d.spend, clk: d.clk, conv: d.conv, scores, overall };
  }).sort((a, b) => b.overall - a.overall);

  const light = s => s >= 70 ? '🟢' : s >= 40 ? '🟡' : '🔴';
  const pillScore = s => {
    const cls = s >= 70 ? 'good' : s >= 40 ? 'watch' : 'bad';
    return `<span class="pill ${cls}">${s.toFixed(0)}</span>`;
  };

  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>Campaign</th>
            <th class="num">CTR</th>
            <th class="num">CVR</th>
            <th class="num">Freq</th>
            <th class="num">VI</th>
            <th class="num">Spend</th>
            <th class="num">Conv.</th>
            <th class="num">CPA</th>
            <th class="num">Health Score ↓</th>
            <th class="num">Status</th>
          </tr>
        </thead>
        <tbody>
          ${campaigns.map(r => `
            <tr>
              <td class="lab">${r.camp}</td>
              <td class="num">${r.ctr.toFixed(2)}%</td>
              <td class="num">${r.cvr.toFixed(2)}%</td>
              <td class="num">${r.freq.toFixed(1)}x</td>
              <td class="num">${r.vi.toFixed(0)}%</td>
              <td class="num">${fmtVND(r.spend)}</td>
              <td class="num">${fmt(r.conv)}</td>
              <td class="num">${fmtVND(r.cpa)}</td>
              <td class="num">${pillScore(r.overall)}</td>
              <td class="num">${light(r.overall)} ${r.overall >= 70 ? 'Healthy' : r.overall >= 40 ? 'Monitor' : 'At Risk'}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  // Store for radar
  window._execCampaigns = campaigns;

  const ic = el('ic_ex_health'), ins = el('ins_ex_health');
  if (ic && ins && campaigns.length > 0) {
    const healthy = campaigns.filter(c => c.overall >= 70).length;
    const atRisk  = campaigns.filter(c => c.overall < 40).length;
    ic.className = atRisk > 0 ? 'insight-ic bad' : 'insight-ic good';
    ic.textContent = atRisk > 0 ? '⚠' : '✓';
    ins.innerHTML = `<b>${healthy}</b> campaign${healthy !== 1 ? 's' : ''} healthy · <b>${atRisk}</b> at risk. `
      + `Top performer: <b>${campaigns[0].camp}</b> (score ${campaigns[0].overall.toFixed(0)}).`;
  }

  return campaigns;
}

/* ── E1-b: Radar Chart — top 3 campaigns ─────────────────────────── */
export function drawRadarChart(campaigns, utils) {
  const { alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_ex_radar');

  const top = (campaigns || []).slice(0, 3);
  if (!top.length) return;

  const canvas = el('ch_ex_radar');
  if (!canvas) return;

  const labels = ['CTR', 'CVR', 'Viewability', 'Freq Score', 'Efficiency'];
  const datasets = top.map((c, i) => ({
    label: c.camp,
    data: [c.scores.ctr, c.scores.cvr, c.scores.vi, c.scores.freq, c.scores.eff],
    borderColor: COLORS[i],
    backgroundColor: alpha(COLORS[i], 0.15),
    borderWidth: 2,
    pointRadius: 4
  }));

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'radar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0, max: 100,
          ticks: { stepSize: 25, font: { size: 9 }, backdropColor: 'transparent' },
          pointLabels: { font: { size: 11 } },
          grid: { color: 'rgba(0,0,0,.08)' }
        }
      },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } }
      }
    }
  });
  registerChart('ch_ex_radar', chart);
}
