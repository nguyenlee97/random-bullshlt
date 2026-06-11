/**
 * conversion/c3-funnel.js
 * C3 — Impression→Click→Conversion funnel + Top Converting Campaigns table
 * Use-case: Where does the conversion funnel lose users most?
 */

function el(id) { return document.getElementById(id); }

/* ── C3-a: Conversion Funnel (HTML bar funnel + doughnut gauge) ──── */
export function drawConversionFunnel(rows, utils) {
  const { fmt } = utils;

  const totImp  = rows.reduce((s, r) => s + r.impressions, 0);
  const totClk  = rows.reduce((s, r) => s + r.clicks, 0);
  const totConv = rows.reduce((s, r) => s + r.conversions, 0);
  const totReach = rows.reduce((s, r) => s + r.reach, 0);

  const ctr  = totImp  > 0 ? totClk  / totImp  * 100 : 0;
  const cvr  = totClk  > 0 ? totConv / totClk  * 100 : 0;
  const e2e  = totImp  > 0 ? totConv / totImp  * 100 : 0; // end-to-end rate

  const stages = [
    { label: 'Impressions served', val: totImp,  pct: 100,  drop: '' },
    { label: 'Unique Reach',       val: totReach, pct: totImp > 0 ? totReach / totImp * 100 : 0, drop: '' },
    { label: 'Clicks',             val: totClk,  pct: totImp > 0 ? ctr : 0, drop: `CTR ${ctr.toFixed(2)}%` },
    { label: 'Conversions',        val: totConv, pct: totImp > 0 ? e2e : 0, drop: `CVR ${cvr.toFixed(2)}% of clicks` }
  ];

  const container = el('cv-funnel');
  if (container) {
    const stageColors = ['#1f3551', '#2c7fb8', '#5ba33d', '#c98a14'];
    container.innerHTML = stages.map((s, i) => `
      <div class="funnel-row">
        <div class="fr-lab">${s.label}</div>
        <div class="fr-bar">
          <span style="width:${Math.min(s.pct, 100).toFixed(1)}%; background:${stageColors[i]}"></span>
        </div>
        <div class="fr-vol">${fmt(s.val)}</div>
        <div class="fr-drop" style="color:var(--muted);font-size:10px">${s.drop}</div>
      </div>`).join('');
  }

  // Mini CVR gauge (doughnut)
  const canvas = el('ch_cv_gauge');
  const existing = canvas ? Chart.getChart(canvas) : null;
  if (existing) existing.destroy();
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Converted', 'Dropped'],
      datasets: [{
        data: [cvr, 100 - cvr],
        backgroundColor: ['rgba(91,163,61,0.85)', 'rgba(221,227,234,0.5)'],
        borderWidth: 0,
        cutout: '72%'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.raw.toFixed(2)}%` } }
      }
    }
  });

  // Inline CVR label
  const lbl = el('cv-gauge-label');
  if (lbl) lbl.textContent = cvr.toFixed(1) + '%';

  const ic = el('ic_cv_funnel'), ins = el('ins_cv_funnel');
  if (ic && ins) {
    ic.className = cvr >= 5 ? 'insight-ic good' : cvr >= 2 ? 'insight-ic warn' : 'insight-ic bad';
    ic.textContent = cvr >= 5 ? '✓' : '⚠';
    ins.innerHTML = `End-to-end funnel: <b>${fmt(totImp)}</b> impressions → <b>${fmt(totClk)}</b> clicks → <b>${fmt(totConv)}</b> conversions. `
      + `Overall e2e rate: <b>${e2e.toFixed(3)}%</b>. The biggest drop is at the <b>click stage</b> — improving CTR has the highest leverage.`;
  }
}

/* ── C3-b: Top Converting Campaigns table ────────────────────────── */
export function renderTopConversionsTable(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = el('cv-top-conv');
  if (!container) return;

  const campMap = {};
  rows.forEach(r => {
    const camp = r.campaignId || 'Unknown';
    if (!campMap[camp]) campMap[camp] = { conv: 0, clk: 0, imp: 0, spend: 0 };
    campMap[camp].conv  += r.conversions;
    campMap[camp].clk   += r.clicks;
    campMap[camp].imp   += r.impressions;
    campMap[camp].spend += r.spend;
  });

  const sorted = Object.entries(campMap)
    .map(([camp, d]) => ({
      camp,
      conv:  d.conv,
      clk:   d.clk,
      imp:   d.imp,
      spend: d.spend,
      cvr:   d.clk > 0 ? d.conv / d.clk * 100 : 0,
      cpa:   d.conv > 0 ? d.spend / d.conv : 0,
      ctr:   d.imp  > 0 ? d.clk / d.imp * 100 : 0
    }))
    .sort((a, b) => b.conv - a.conv);

  const medal = i => ['🥇', '🥈', '🥉'][i] || String(i + 1);
  const pillCvr = v => {
    const cls = v >= 5 ? 'good' : v >= 2 ? 'watch' : 'bad';
    return `<span class="pill ${cls}">${v.toFixed(2)}%</span>`;
  };

  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Campaign</th>
            <th class="num">Impressions</th>
            <th class="num">Clicks</th>
            <th class="num">CTR</th>
            <th class="num">Conversions ↓</th>
            <th class="num">CVR</th>
            <th class="num">Spend</th>
            <th class="num">CPA</th>
          </tr>
        </thead>
        <tbody>
          ${sorted.map((r, i) => `
            <tr>
              <td class="ctr">${medal(i)}</td>
              <td class="lab">${r.camp}</td>
              <td class="num">${fmt(r.imp)}</td>
              <td class="num">${fmt(r.clk)}</td>
              <td class="num">${r.ctr.toFixed(2)}%</td>
              <td class="num" style="font-weight:700;color:var(--green-d)">${fmt(r.conv)}</td>
              <td class="num">${pillCvr(r.cvr)}</td>
              <td class="num">${fmtVND(r.spend)}</td>
              <td class="num">${fmtVND(r.cpa)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  const ic = el('ic_cv_top'), ins = el('ins_cv_top');
  if (ic && ins && sorted.length > 0) {
    const top = sorted[0];
    ic.className = 'insight-ic good'; ic.textContent = '🥇';
    ins.innerHTML = `<b>${top.camp}</b> leads with <b>${fmt(top.conv)}</b> conversions at CVR <b>${top.cvr.toFixed(2)}%</b> and CPA <b>${fmtVND(top.cpa)}</b>.`;
  }
}
