/**
 * executive/e4-recommendations.js
 * E4 — Auto-generated Alerts & Action Recommendations
 * Scans all KPI thresholds and emits prioritised action cards
 */

export function renderRecommendations(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = document.getElementById('ex-recommendations');
  if (!container) return;

  const totImp   = rows.reduce((s, r) => s + r.impressions, 0);
  const totReach = rows.reduce((s, r) => s + r.reach, 0);
  const totClk   = rows.reduce((s, r) => s + r.clicks, 0);
  const totConv  = rows.reduce((s, r) => s + r.conversions, 0);
  const totSpend = rows.reduce((s, r) => s + r.spend, 0);
  const avgFreq  = totReach > 0 ? totImp / totReach : 0;
  const avgCTR   = totImp  > 0 ? totClk  / totImp  * 100 : 0;
  const avgCVR   = totClk  > 0 ? totConv / totClk  * 100 : 0;
  const avgVI    = rows.length > 0 ? rows.reduce((s, r) => s + r.vi, 0) / rows.length : 0;

  // Placement data for placement-specific alerts
  const plMap = {};
  rows.forEach(r => {
    const pl = r.zone || 'Unknown';
    if (!plMap[pl]) plMap[pl] = { imp: 0, reach: 0, clk: 0, conv: 0, spend: 0, vi: 0, n: 0 };
    plMap[pl].imp   += r.impressions;
    plMap[pl].reach += r.reach;
    plMap[pl].clk   += r.clicks;
    plMap[pl].conv  += r.conversions;
    plMap[pl].spend += r.spend;
    plMap[pl].vi    += r.vi;
    plMap[pl].n++;
  });

  const placements = Object.entries(plMap).map(([pl, d]) => ({
    pl, freq: d.reach > 0 ? d.imp / d.reach : 0,
    ctr: d.imp > 0 ? d.clk / d.imp * 100 : 0,
    vi:  d.n   > 0 ? d.vi / d.n : 0,
    cpa: d.conv > 0 ? d.spend / d.conv : 0,
    conv: d.conv, spend: d.spend
  }));

  // CTR decay (first 7 days vs last 7 days)
  const dateMap = {};
  rows.forEach(r => {
    if (!dateMap[r.date]) dateMap[r.date] = { imp: 0, clk: 0 };
    dateMap[r.date].imp += r.impressions;
    dateMap[r.date].clk += r.clicks;
  });
  const dates = Object.keys(dateMap).sort();
  const early = dates.slice(0, 7).map(d => dateMap[d].imp > 0 ? dateMap[d].clk / dateMap[d].imp * 100 : 0);
  const late  = dates.slice(-7).map(d => dateMap[d].imp > 0 ? dateMap[d].clk / dateMap[d].imp * 100 : 0);
  const eAvg  = early.reduce((s, v) => s + v, 0) / (early.length || 1);
  const lAvg  = late.reduce((s, v)  => s + v, 0) / (late.length  || 1);
  const ctrDecayPct = eAvg > 0 ? (lAvg - eAvg) / eAvg * 100 : 0;

  const overFreqPl = placements.filter(p => p.freq > 5).sort((a, b) => b.freq - a.freq);
  const lowVIPl    = placements.filter(p => p.vi < 50).sort((a, b) => a.vi - b.vi);
  const highCpaPl  = placements.filter(p => p.cpa > 0).sort((a, b) => b.cpa - a.cpa).slice(0, 3);
  const avgCpa     = totConv > 0 ? totSpend / totConv : 0;

  // Build alert list
  const alerts = [];

  // Priority 1 — Critical
  if (overFreqPl.length > 0) {
    alerts.push({
      priority: 'critical', icon: '🔴',
      title: `Frequency cap needed on ${overFreqPl.length} placement${overFreqPl.length > 1 ? 's' : ''}`,
      body: `<b>${overFreqPl.map(p => p.pl).join(', ')}</b> exceed 5x frequency. Immediate risk of ad fatigue and brand damage. Set max frequency cap of 3–5x per user per day.`,
      action: 'Apply frequency cap in campaign settings'
    });
  }

  if (ctrDecayPct < -20) {
    alerts.push({
      priority: 'critical', icon: '🔴',
      title: `Creative fatigue: CTR down ${Math.abs(ctrDecayPct).toFixed(0)}% from launch`,
      body: `Opening week avg CTR was <b>${eAvg.toFixed(2)}%</b>, now <b>${lAvg.toFixed(2)}%</b>. Significant creative wear detected across the campaign.`,
      action: 'Rotate creatives — upload at least 2 new variants per placement'
    });
  }

  if (lowVIPl.length > 0) {
    alerts.push({
      priority: 'critical', icon: '🔴',
      title: `${lowVIPl.length} placement${lowVIPl.length > 1 ? 's' : ''} below 50% viewability threshold`,
      body: `Non-viewable inventory at <b>${lowVIPl.map(p => `${p.pl} (${p.vi.toFixed(0)}%)`).join(', ')}</b>. Spend is wasted on unseen impressions.`,
      action: 'Pause these placements immediately and negotiate viewability guarantees'
    });
  }

  // Priority 2 — Warning
  if (avgFreq > 3 && avgFreq <= 5) {
    alerts.push({
      priority: 'warning', icon: '🟡',
      title: `Moderate over-frequency — avg ${avgFreq.toFixed(1)}x`,
      body: 'Average frequency is approaching the 5x threshold. Monitor daily and apply frequency caps if it continues rising.',
      action: 'Set frequency cap at 5x and monitor for next 7 days'
    });
  }

  if (ctrDecayPct < -10 && ctrDecayPct >= -20) {
    alerts.push({
      priority: 'warning', icon: '🟡',
      title: `Mild CTR decay: ${ctrDecayPct.toFixed(0)}% from baseline`,
      body: `CTR trending downward. Early stage of creative fatigue. A/B test a new creative variant before full decay sets in.`,
      action: 'A/B test 1 new creative variant on top 2 placements'
    });
  }

  if (avgCVR < 2) {
    alerts.push({
      priority: 'warning', icon: '🟡',
      title: `Low conversion rate — avg CVR ${avgCVR.toFixed(2)}%`,
      body: 'Click-to-conversion rate is below the 2% benchmark. Post-click experience (landing page, offer, load speed) may be limiting conversions.',
      action: 'Audit landing page UX and A/B test the offer'
    });
  }

  if (avgVI < 70 && avgVI >= 50) {
    alerts.push({
      priority: 'warning', icon: '🟡',
      title: `Viewability below 70% benchmark — avg ${avgVI.toFixed(0)}%`,
      body: 'While above the minimum, viewability has room for improvement. Prioritise above-the-fold placements.',
      action: 'Shift budget toward placements with VI ≥70%'
    });
  }

  // Priority 3 — Opportunities
  const bestPl = placements.filter(p => p.ctr > avgCTR * 1.5 && p.conv > 0).sort((a, b) => b.conv - a.conv)[0];
  if (bestPl) {
    alerts.push({
      priority: 'opportunity', icon: '🟢',
      title: `Scale opportunity: ${bestPl.pl}`,
      body: `CTR <b>${bestPl.ctr.toFixed(2)}%</b> (${(bestPl.ctr / avgCTR).toFixed(1)}× avg) with <b>${fmt(bestPl.conv)}</b> conversions. This placement is outperforming — increase budget allocation.`,
      action: 'Increase budget allocation by 20–30% on this placement'
    });
  }

  if (avgCTR >= 0.8) {
    alerts.push({
      priority: 'opportunity', icon: '🟢',
      title: `Strong CTR — consider scaling reach`,
      body: `Campaign-wide CTR <b>${avgCTR.toFixed(2)}%</b> exceeds the 0.8% benchmark. Creative is resonating — expand audience targeting or add new placements.`,
      action: 'Expand to 2–3 new placements on top-performing channels'
    });
  }

  if (!alerts.length) {
    alerts.push({
      priority: 'opportunity', icon: '✅',
      title: 'No critical issues detected',
      body: 'All key metrics are within healthy ranges. Continue monitoring weekly.',
      action: 'Review again after next 7-day period'
    });
  }

  const priorityOrder = { critical: 0, warning: 1, opportunity: 2 };
  alerts.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);

  const bgMap = { critical: '#fff5f5', warning: '#fffbf0', opportunity: '#f0fff4' };
  const borderMap = { critical: '#e74c3c', warning: '#c98a14', opportunity: '#5ba33d' };

  container.innerHTML = alerts.map(a => `
    <div class="rec-card" style="border-left:4px solid ${borderMap[a.priority]};background:${bgMap[a.priority]}">
      <div class="rec-head">
        <span class="rec-icon">${a.icon}</span>
        <span class="rec-title">${a.title}</span>
        <span class="rec-badge" style="background:${borderMap[a.priority]}20;color:${borderMap[a.priority]};border:1px solid ${borderMap[a.priority]}40">
          ${a.priority.toUpperCase()}
        </span>
      </div>
      <div class="rec-body">${a.body}</div>
      <div class="rec-action"><b>→ Action:</b> ${a.action}</div>
    </div>`).join('');
}
