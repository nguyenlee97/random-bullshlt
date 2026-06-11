/**
 * awareness/scorecard.js
 * KPI scorecard row for the Awareness tab
 * Metrics: Total Reach, Avg Frequency, Avg CPM, Avg Viewability (VI)
 */

export function renderScorecard(rows, utils) {
  const { fmt, fmtVND } = utils;
  const panel = document.getElementById('aw-scorecard');
  if (!panel) return;

  const totImp   = rows.reduce((s, r) => s + r.impressions, 0);
  const totReach = rows.reduce((s, r) => s + r.reach, 0);
  const totSpend = rows.reduce((s, r) => s + r.spend, 0);
  const avgFreq  = totReach > 0 ? totImp / totReach : 0;
  const avgCPM   = rows.length > 0
    ? rows.reduce((s, r) => s + r.cpm, 0) / rows.length
    : 0;
  const avgVI    = rows.length > 0
    ? rows.reduce((s, r) => s + r.vi, 0) / rows.length
    : 0;

  // VI benchmark: <50 bad, 50-70 watch, >70 good
  const viClass  = avgVI >= 70 ? 'good' : avgVI >= 50 ? 'watch' : 'bad';
  const freqClass = avgFreq <= 3 ? 'good' : avgFreq <= 5 ? 'watch' : 'bad';

  const kpis = [
    {
      label: 'Total Reach',
      val: fmt(totReach),
      delta: `${(totReach > 0 ? (totReach / totImp * 100) : 0).toFixed(1)}% of impressions are unique`,
      cls: 'neutral'
    },
    {
      label: 'Total Impressions',
      val: fmt(totImp),
      delta: null,
      cls: 'neutral'
    },
    {
      label: 'Avg Frequency',
      val: avgFreq.toFixed(2) + 'x',
      delta: avgFreq <= 3 ? '✔ Healthy (≤3)' : avgFreq <= 5 ? '⚠ Moderate' : '⚠ Over-frequency risk',
      cls: freqClass
    },
    {
      label: 'Avg CPM',
      val: '₫' + Math.round(avgCPM).toLocaleString('vi-VN'),
      delta: null,
      cls: 'neutral'
    },
    {
      label: 'Total Spend',
      val: fmtVND(totSpend),
      delta: null,
      cls: 'neutral'
    },
    {
      label: 'Avg Viewability (VI)',
      val: avgVI.toFixed(1) + '%',
      delta: avgVI >= 70 ? '✔ Good' : avgVI >= 50 ? '⚠ Below benchmark' : '✘ Poor',
      cls: viClass
    }
  ];

  panel.innerHTML = kpis.map(k => `
    <div class="sc-item">
      <div class="sc-label">${k.label}</div>
      <div class="sc-val">${k.val}</div>
      ${k.delta ? `<div class="sc-delta ${k.cls}">${k.delta}</div>` : ''}
    </div>
  `).join('');
}
