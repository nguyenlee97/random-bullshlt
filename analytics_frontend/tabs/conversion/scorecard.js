/**
 * conversion/scorecard.js
 * KPI scorecard for the Conversion tab
 * Metrics: Total Conversions, Avg CVR, CPA, Est. ROAS, Top Converting Campaign
 */
export function renderScorecard(rows, utils) {
  const { fmt, fmtVND } = utils;
  const panel = document.getElementById('cv-scorecard');
  if (!panel) return;

  const totConv  = rows.reduce((s, r) => s + r.conversions, 0);
  const totClk   = rows.reduce((s, r) => s + r.clicks, 0);
  const totImp   = rows.reduce((s, r) => s + r.impressions, 0);
  const totSpend = rows.reduce((s, r) => s + r.spend, 0);
  const avgCVR   = totClk > 0 ? totConv / totClk * 100 : 0;
  const cpa      = totConv > 0 ? totSpend / totConv : 0;
  // Estimate ROAS: assume avg conversion value = 5× CPA (proxy when no revenue data)
  const estROAS  = cpa > 0 ? 5 : 0;

  // Top campaign by conversions
  const campMap = {};
  rows.forEach(r => {
    campMap[r.campaignId] = (campMap[r.campaignId] || 0) + r.conversions;
  });
  const topCamp = Object.entries(campMap).sort((a, b) => b[1] - a[1])[0] || ['—', 0];

  // CVR health
  const cvrCls = avgCVR >= 5 ? 'good' : avgCVR >= 2 ? 'watch' : 'bad';

  const kpis = [
    { label: 'Total Conversions', val: fmt(totConv), delta: null },
    { label: 'Total Clicks',      val: fmt(totClk),  delta: null },
    {
      label: 'Avg CVR',
      val: avgCVR.toFixed(2) + '%',
      delta: avgCVR >= 5 ? '✔ Strong' : avgCVR >= 2 ? '⚠ Average' : '✘ Low',
      cls: cvrCls
    },
    {
      label: 'Cost per Conversion',
      val: fmtVND(cpa),
      delta: null
    },
    {
      label: 'Est. ROAS',
      val: estROAS > 0 ? estROAS.toFixed(1) + 'x' : 'N/A',
      delta: 'Proxy estimate (5× CPA)',
      cls: 'neutral'
    },
    {
      label: 'Top Converting Campaign',
      val: topCamp[0],
      delta: `${fmt(topCamp[1])} conversions`,
      cls: 'good'
    }
  ];

  panel.innerHTML = kpis.map(k => `
    <div class="sc-item">
      <div class="sc-label">${k.label}</div>
      <div class="sc-val" style="font-size:${String(k.val).length > 12 ? '14px' : '20px'}">${k.val}</div>
      ${k.delta ? `<div class="sc-delta ${k.cls || ''}">${k.delta}</div>` : ''}
    </div>`).join('');
}
