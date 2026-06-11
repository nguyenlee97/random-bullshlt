/**
 * executive/scorecard.js
 * Top-line business KPI scorecard for the Executive tab
 */
export function renderScorecard(rows, utils) {
  const { fmt, fmtVND } = utils;
  const panel = document.getElementById('ex-scorecard');
  if (!panel) return;

  const totImp   = rows.reduce((s, r) => s + r.impressions, 0);
  const totReach = rows.reduce((s, r) => s + r.reach, 0);
  const totClk   = rows.reduce((s, r) => s + r.clicks, 0);
  const totConv  = rows.reduce((s, r) => s + r.conversions, 0);
  const totSpend = rows.reduce((s, r) => s + r.spend, 0);
  const avgCTR   = totImp  > 0 ? totClk  / totImp  * 100 : 0;
  const avgCVR   = totClk  > 0 ? totConv / totClk  * 100 : 0;
  const cpa      = totConv > 0 ? totSpend / totConv : 0;
  const avgFreq  = totReach > 0 ? totImp / totReach : 0;
  const avgVI    = rows.length > 0 ? rows.reduce((s, r) => s + r.vi, 0) / rows.length : 0;

  const kpis = [
    { label: 'Total Spend',      val: fmtVND(totSpend),          sub: null },
    { label: 'Total Impressions', val: fmt(totImp),               sub: null },
    { label: 'Total Reach',      val: fmt(totReach),
      sub: `Avg freq ${avgFreq.toFixed(1)}x`, cls: avgFreq <= 3 ? 'good' : avgFreq <= 5 ? 'watch' : 'bad' },
    { label: 'Total Clicks',     val: fmt(totClk),               sub: null },
    { label: 'Avg CTR',          val: avgCTR.toFixed(2) + '%',
      sub: avgCTR >= 0.8 ? '✔ Above target' : avgCTR >= 0.4 ? '⚠ Average' : '✘ Below target',
      cls: avgCTR >= 0.8 ? 'good' : avgCTR >= 0.4 ? 'watch' : 'bad' },
    { label: 'Conversions',      val: fmt(totConv),              sub: null },
    { label: 'Avg CVR',          val: avgCVR.toFixed(2) + '%',
      sub: avgCVR >= 5 ? '✔ Strong' : avgCVR >= 2 ? '⚠ Average' : '✘ Low',
      cls: avgCVR >= 5 ? 'good' : avgCVR >= 2 ? 'watch' : 'bad' },
    { label: 'Cost per Conversion', val: fmtVND(cpa),            sub: null },
    { label: 'Avg Viewability',  val: avgVI.toFixed(1) + '%',
      sub: avgVI >= 70 ? '✔ Good' : avgVI >= 50 ? '⚠ Monitor' : '✘ Poor',
      cls: avgVI >= 70 ? 'good' : avgVI >= 50 ? 'watch' : 'bad' },
  ];

  panel.innerHTML = `<div class="ex-kpi-grid">${kpis.map(k => `
    <div class="sc-item">
      <div class="sc-label">${k.label}</div>
      <div class="sc-val" style="font-size:${String(k.val).length > 8 ? '18px' : '22px'}">${k.val}</div>
      ${k.sub ? `<div class="sc-delta ${k.cls || ''}">${k.sub}</div>` : ''}
    </div>`).join('')}</div>`;
}
