const METRIC_DEFINITIONS = Object.freeze({
  impressions: { label: 'Impressions', unit: 'count', formula: 'sum(impressions)' },
  clicks: { label: 'Clicks', unit: 'count', formula: 'sum(clicks)' },
  spend: { label: 'Spend', unit: 'VND', formula: 'sum(spend)' },
  conversions: { label: 'Conversions', unit: 'count', formula: 'sum(conversions)' },
  ctr: { label: 'CTR', unit: 'percent', formula: 'clicks / impressions * 100' },
  cpm: { label: 'CPM', unit: 'VND', formula: 'spend / impressions * 1000' },
  cpa: { label: 'CPA', unit: 'VND', formula: 'spend / conversions' },
  click_conversion_rate: { label: 'Click conversion rate', unit: 'percent', formula: 'conversions / clicks * 100' },
  viewability: { label: 'Viewability', unit: 'percent', formula: 'impression-weighted mean(vi)' },
  summed_daily_reach: {
    label: 'Summed daily reach estimate', unit: 'count', formula: 'sum(daily reach)',
    limitation: 'Not deduplicated across dates; never present as campaign unique reach.',
  },
});

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round((Number(value) || 0) * factor) / factor;
}

function aggregate(records) {
  const totals = records.reduce((acc, row) => {
    const impressions = Number(row.impressions) || 0;
    acc.impressions += impressions;
    acc.clicks += Number(row.clicks) || 0;
    acc.spend += Number(row.spend) || 0;
    acc.conversions += Number(row.conversions) || 0;
    acc.summed_daily_reach += Number(row.reach) || 0;
    acc.weightedVi += (Number(row.vi) || 0) * impressions;
    return acc;
  }, { impressions: 0, clicks: 0, spend: 0, conversions: 0, summed_daily_reach: 0, weightedVi: 0 });
  return {
    impressions: round(totals.impressions, 0),
    clicks: round(totals.clicks, 0),
    spend: round(totals.spend, 0),
    conversions: round(totals.conversions, 0),
    ctr: round(totals.impressions ? totals.clicks / totals.impressions * 100 : 0),
    cpm: round(totals.impressions ? totals.spend / totals.impressions * 1000 : 0),
    cpa: totals.conversions ? round(totals.spend / totals.conversions, 0) : null,
    click_conversion_rate: totals.clicks ? round(totals.conversions / totals.clicks * 100) : null,
    viewability: totals.impressions ? round(totals.weightedVi / totals.impressions) : null,
    summed_daily_reach: round(totals.summed_daily_reach, 0),
  };
}

function finding(id, scope, metrics, interpretation, confidence = 'high') {
  return { id, scope, metrics, interpretation, confidence };
}

function buildReportContract(campaign, records) {
  const dates = records.map(row => String(row.date || '')).filter(Boolean).sort();
  const timeframe = { start: dates[0] || null, end: dates.at(-1) || null };
  const totals = aggregate(records);
  const byZoneRows = new Map();
  records.forEach(row => {
    const id = String(row.placementId || 'unknown');
    if (!byZoneRows.has(id)) byZoneRows.set(id, []);
    byZoneRows.get(id).push(row);
  });
  const zones = [...byZoneRows.entries()].map(([zoneId, rows]) => ({ zoneId, ...aggregate(rows) }));
  const bestCtr = zones.filter(item => item.impressions > 0).sort((a, b) => b.ctr - a.ctr)[0] || null;
  const bestCpm = zones.filter(item => item.impressions > 0).sort((a, b) => a.cpm - b.cpm)[0] || null;

  const uniqueDates = [...new Set(dates)];
  const midpoint = Math.ceil(uniqueDates.length / 2);
  const firstDates = new Set(uniqueDates.slice(0, midpoint));
  const first = aggregate(records.filter(row => firstDates.has(String(row.date || ''))));
  const second = aggregate(records.filter(row => !firstDates.has(String(row.date || ''))));
  const findings = [
    finding('campaign_totals', 'campaign', totals, 'Measured and computed campaign totals for the stated timeframe.'),
    finding('period_comparison', 'campaign', { first_period: first, second_period: second }, 'First and second period comparison; no causal claim.'),
  ];
  if (bestCtr) findings.push(finding('top_zone_ctr', bestCtr.zoneId, bestCtr, 'Highest observed CTR among zones with delivery.', 'medium'));
  if (bestCpm) findings.push(finding('lowest_zone_cpm', bestCpm.zoneId, bestCpm, 'Lowest observed CPM among zones with delivery.', 'medium'));

  return {
    contractVersion: 'report-evidence-v1',
    source: 'synthetic_showcase',
    synthetic: true,
    syntheticLabel: 'Dữ liệu mô phỏng (showcase) — không phải kết quả delivery thực tế',
    campaignId: campaign.campaignId,
    objective: campaign.objective,
    timeframe,
    metricDefinitions: METRIC_DEFINITIONS,
    findings,
    limitations: [
      'All analytics records are synthetic showcase data generated for product demonstration.',
      'Observed association does not establish causality.',
      'Summed daily reach is not campaign unique reach across the full timeframe.',
      'Recommendations are bounded proposals for operator review, not autonomous campaign changes.',
    ],
  };
}

function validateAnalysisResult(result, expectedQuestions, contract) {
  if (!result || typeof result !== 'object' || typeof result.overall !== 'string') {
    throw new Error('report analysis must contain an overall string');
  }
  const byId = new Map((result.questions || []).map(item => [item.id, item]));
  const findingIds = new Set(contract.findings.map(item => item.id));
  for (const expected of expectedQuestions) {
    const item = byId.get(expected.id);
    if (!item || !item.answer || !Array.isArray(item.answer.sections)) {
      throw new Error(`report analysis missing structured answer for ${expected.id}`);
    }
    if (!Array.isArray(item.findingIds) || !item.findingIds.length) {
      throw new Error(`report analysis missing evidence citations for ${expected.id}`);
    }
    const invented = item.findingIds.filter(id => !findingIds.has(id));
    if (invented.length) throw new Error(`report analysis cited unknown findings: ${invented.join(',')}`);
    for (const section of item.answer.sections) {
      if (!['summary', 'metrics', 'insight', 'recommendation', 'comparison', 'limitation'].includes(section.type)) {
        throw new Error(`unsupported report section type: ${section.type}`);
      }
      if (section.type === 'metrics') {
        for (const metric of section.items || []) {
          if (!metric.metricId || !METRIC_DEFINITIONS[metric.metricId]) {
            throw new Error(`report analysis invented metric: ${metric.metricId || metric.label || 'unknown'}`);
          }
        }
      }
    }
  }
  return result;
}

module.exports = { METRIC_DEFINITIONS, aggregate, buildReportContract, validateAnalysisResult };
