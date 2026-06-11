/**
 * consideration/scorecard.js
 * KPI scorecard for the Consideration tab
 * Metrics: Total Clicks, Avg CTR, Best CTR placement, Top format CTR, Spend/Click
 */
export function renderScorecard(rows, utils) {
  const { fmt, fmtVND } = utils;
  const panel = document.getElementById('co-scorecard');
  if (!panel) return;

  const totImp   = rows.reduce((s, r) => s + r.impressions, 0);
  const totClk   = rows.reduce((s, r) => s + r.clicks, 0);
  const totSpend = rows.reduce((s, r) => s + r.spend, 0);
  const avgCTR   = totImp > 0 ? totClk / totImp * 100 : 0;
  const cpc      = totClk > 0 ? totSpend / totClk : 0;

  // Best placement by CTR
  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { imp: 0, clk: 0 };
    plMap[pl].imp += r.impressions;
    plMap[pl].clk += r.clicks;
  });
  const bestPl = Object.entries(plMap)
    .filter(([, d]) => d.imp > 0)
    .map(([pl, d]) => ({ pl, ctr: d.clk / d.imp * 100 }))
    .sort((a, b) => b.ctr - a.ctr)[0] || { pl: '—', ctr: 0 };

  // Best format by CTR
  const fmtMap = {};
  rows.forEach(r => {
    const f = r.format || 'unknown';
    if (!fmtMap[f]) fmtMap[f] = { imp: 0, clk: 0 };
    fmtMap[f].imp += r.impressions;
    fmtMap[f].clk += r.clicks;
  });
  const bestFmt = Object.entries(fmtMap)
    .filter(([, d]) => d.imp > 0)
    .map(([f, d]) => ({ f, ctr: d.clk / d.imp * 100 }))
    .sort((a, b) => b.ctr - a.ctr)[0] || { f: '—', ctr: 0 };

  const ctrCls = avgCTR >= 0.8 ? 'good' : avgCTR >= 0.4 ? 'watch' : 'bad';

  const kpis = [
    { label: 'Total Clicks',    val: fmt(totClk),                          delta: null },
    { label: 'Total Impressions', val: fmt(totImp),                        delta: null },
    { label: 'Avg CTR',         val: avgCTR.toFixed(2) + '%',
      delta: avgCTR >= 0.8 ? '✔ Above benchmark' : avgCTR >= 0.4 ? '⚠ Average' : '✘ Below target',
      cls: ctrCls },
    { label: 'Cost per Click',  val: fmtVND(cpc),                          delta: null },
    { label: 'Best Placement',  val: bestPl.pl, delta: `CTR ${bestPl.ctr.toFixed(2)}%`, cls: 'good' },
    { label: 'Best Format',     val: bestFmt.f, delta: `CTR ${bestFmt.ctr.toFixed(2)}%`, cls: 'good' },
  ];

  panel.innerHTML = kpis.map(k => `
    <div class="sc-item">
      <div class="sc-label">${k.label}</div>
      <div class="sc-val" style="font-size:${k.val.length > 12 ? '14px' : '20px'}">${k.val}</div>
      ${k.delta ? `<div class="sc-delta ${k.cls || ''}">${k.delta}</div>` : ''}
    </div>`).join('');
}
