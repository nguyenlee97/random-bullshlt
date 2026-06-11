/**
 * retention/scorecard.js
 * KPI scorecard for the Retention tab
 * Metrics: Re-exposure Rate, Avg Frequency, WoW Reach Growth, CTR Decay, Top Saturated Placement
 */
export function renderScorecard(rows, utils) {
  const { fmt } = utils;
  const panel = document.getElementById('rt-scorecard');
  if (!panel) return;

  const totImp   = rows.reduce((s, r) => s + r.impressions, 0);
  const totReach = rows.reduce((s, r) => s + r.reach, 0);
  const avgFreq  = totReach > 0 ? totImp / totReach : 0;
  // Re-exposure rate = (impressions - reach) / impressions → % of imps shown to repeat users
  const reExpRate = totImp > 0 ? (totImp - totReach) / totImp * 100 : 0;

  // WoW reach: compare last 7 days vs prior 7 days
  const dateMap = {};
  rows.forEach(r => { dateMap[r.date] = (dateMap[r.date] || 0) + r.reach; });
  const dates = Object.keys(dateMap).sort();
  const last7  = dates.slice(-7).reduce((s, d) => s + dateMap[d], 0);
  const prior7 = dates.slice(-14, -7).reduce((s, d) => s + (dateMap[d] || 0), 0);
  const wowDelta = prior7 > 0 ? (last7 - prior7) / prior7 * 100 : 0;

  // CTR decay: compare first-week avg CTR to last-week
  const impMap = {}, clkMap = {};
  rows.forEach(r => {
    impMap[r.date] = (impMap[r.date] || 0) + r.impressions;
    clkMap[r.date] = (clkMap[r.date] || 0) + r.clicks;
  });
  const ctrs = dates.map(d => impMap[d] > 0 ? clkMap[d] / impMap[d] * 100 : 0);
  const firstWeekCTR = ctrs.slice(0, 7).reduce((s, v) => s + v, 0) / Math.min(7, ctrs.length);
  const lastWeekCTR  = ctrs.slice(-7).reduce((s, v) => s + v, 0) / Math.min(7, ctrs.length);
  const ctrDecay = firstWeekCTR > 0 ? (lastWeekCTR - firstWeekCTR) / firstWeekCTR * 100 : 0;

  // Most saturated placement (highest avg frequency)
  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { imp: 0, reach: 0 };
    plMap[pl].imp   += r.impressions;
    plMap[pl].reach += r.reach;
  });
  const mostSat = Object.entries(plMap)
    .filter(([, d]) => d.reach > 0)
    .map(([pl, d]) => ({ pl, freq: d.imp / d.reach }))
    .sort((a, b) => b.freq - a.freq)[0] || { pl: '—', freq: 0 };

  const freqCls  = avgFreq <= 3 ? 'good' : avgFreq <= 5 ? 'watch' : 'bad';
  const wowCls   = wowDelta >= 0 ? 'good' : 'bad';
  const decayCls = ctrDecay >= 0 ? 'good' : ctrDecay > -15 ? 'watch' : 'bad';

  const kpis = [
    {
      label: 'Re-exposure Rate',
      val: reExpRate.toFixed(1) + '%',
      delta: 'Repeat impressions / total imps',
      cls: 'neutral'
    },
    {
      label: 'Avg Frequency',
      val: avgFreq.toFixed(2) + 'x',
      delta: avgFreq <= 3 ? '✔ Healthy' : avgFreq <= 5 ? '⚠ Moderate' : '✘ Over-exposed',
      cls: freqCls
    },
    {
      label: 'WoW Reach Growth',
      val: (wowDelta >= 0 ? '+' : '') + wowDelta.toFixed(1) + '%',
      delta: `Last 7d: ${fmt(last7)} vs Prior 7d: ${fmt(prior7)}`,
      cls: wowCls
    },
    {
      label: 'CTR Decay (Period)',
      val: (ctrDecay >= 0 ? '+' : '') + ctrDecay.toFixed(1) + '%',
      delta: ctrDecay < -15 ? '✘ Creative fatigue' : ctrDecay < 0 ? '⚠ Mild decay' : '✔ Holding',
      cls: decayCls
    },
    {
      label: 'Most Saturated Placement',
      val: mostSat.pl,
      delta: `Freq ${mostSat.freq.toFixed(1)}x avg`,
      cls: mostSat.freq > 5 ? 'bad' : 'watch'
    },
    {
      label: 'Total Reach',
      val: fmt(totReach),
      delta: null
    }
  ];

  panel.innerHTML = kpis.map(k => `
    <div class="sc-item">
      <div class="sc-label">${k.label}</div>
      <div class="sc-val" style="font-size:${String(k.val).length > 10 ? '15px' : '20px'}">${k.val}</div>
      ${k.delta ? `<div class="sc-delta ${k.cls || ''}">${k.delta}</div>` : ''}
    </div>`).join('');
}
