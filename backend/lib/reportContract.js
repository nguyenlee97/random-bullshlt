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

function buildLegacyReportContract(campaign, records) {
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

function aggregateOutcomes(records, measurementSpec) {
  const totals = aggregate(records);
  const outcomes = {};
  for (const event of measurementSpec.outcomeGraph?.events || []) outcomes[event.id] = 0;
  for (const row of records) {
    for (const eventId of Object.keys(outcomes)) {
      outcomes[eventId] += Number(row.outcomes?.[eventId]) || 0;
    }
  }
  return { ...totals, outcomes };
}

function actualForKpi(kpi, totals) {
  if (kpi.metric === 'media_metric') return totals[kpi.metricId] ?? null;
  if (kpi.metric === 'event_count') return totals.outcomes[kpi.eventId] || 0;
  if (kpi.metric === 'cost_per_event') {
    const count = totals.outcomes[kpi.eventId] || 0;
    return count ? round(totals.spend / count, 0) : null;
  }
  if (kpi.metric === 'event_rate') {
    const numerator = totals.outcomes[kpi.numeratorEvent] || 0;
    const denominator = totals.outcomes[kpi.denominatorEvent] || 0;
    return denominator ? round(numerator / denominator * 100) : null;
  }
  return null;
}

function statusFor(actual, target, operator) {
  if (!Number.isFinite(actual) || !Number.isFinite(target) || target <= 0) return 'watch';
  const meets = operator === '<=' ? actual <= target : actual >= target;
  if (meets) return 'good';
  const attainment = operator === '<=' ? target / Math.max(actual, 1) : actual / target;
  return attainment >= 0.85 ? 'watch' : 'bad';
}

function evaluateKpis(measurementSpec, totals) {
  return (measurementSpec.kpis || []).map(kpi => {
    const actual = actualForKpi(kpi, totals);
    const status = statusFor(actual, Number(kpi.target), kpi.operator);
    const attainment = Number.isFinite(actual) && Number(kpi.target) > 0
      ? (kpi.operator === '<=' ? Number(kpi.target) / Math.max(actual, 1) : actual / Number(kpi.target))
      : null;
    return {
      ...kpi,
      actual,
      status,
      attainment: attainment === null ? null : round(attainment * 100, 1),
      gap: Number.isFinite(actual) ? round(actual - Number(kpi.target), kpi.unit === 'percent' ? 2 : 0) : null,
      evidenceId: 'kpi_scorecard',
    };
  });
}

function overallPerformance(kpiScorecard) {
  const counts = { good: 0, watch: 0, bad: 0 };
  for (const kpi of kpiScorecard) counts[kpi.status] += 1;
  const status = counts.bad ? 'bad' : counts.watch ? 'watch' : counts.good ? 'good' : 'watch';
  const summary = kpiScorecard.length
    ? `${counts.good} KPI đạt, ${counts.watch} KPI cần theo dõi, ${counts.bad} KPI chưa đạt.`
    : 'Chưa có KPI mục tiêu đủ cấu trúc để đánh giá đạt/chưa đạt.';
  return { status, counts, summary, evaluatedKpis: kpiScorecard.length };
}

function buildActions(kpiScorecard, measurementSpec, zones) {
  const eventById = new Map((measurementSpec.outcomeGraph?.events || []).map(item => [item.id, item]));
  const topZone = zones.filter(item => item.impressions > 0).sort((a, b) => b.ctr - a.ctr)[0];
  const actions = [];
  for (const kpi of kpiScorecard.filter(item => item.status !== 'good')) {
    const eventId = kpi.eventId || kpi.numeratorEvent;
    const eventLabel = eventById.get(eventId)?.label || eventId || kpi.label;
    let proposedAction;
    let expectedMovement;
    let guardrail;
    if (kpi.metric === 'media_metric') {
      proposedAction = `Điều chỉnh phân bổ theo zone và thử nghiệm creative có kiểm soát để cải thiện ${kpi.label}.`;
      expectedMovement = `Đưa ${kpi.label} từ ${kpi.actual ?? 'N/A'} về phía mục tiêu ${kpi.operator} ${kpi.target}.`;
      guardrail = 'Theo dõi đồng thời delivery volume và KPI chính của objective; không tối ưu một metric đơn lẻ.';
    } else if (kpi.metric === 'event_rate') {
      proposedAction = `Rà soát SLA follow-up và điểm rơi nhắc lịch cho ${eventLabel}; thử nghiệm theo cohort thay vì tăng media đồng loạt.`;
      expectedMovement = `Tăng ${kpi.label} từ ${kpi.actual ?? 'N/A'}% về phía mục tiêu ${kpi.target}%.`;
      guardrail = 'Không đánh đổi chất lượng lead; theo dõi tỷ lệ hủy và trùng lead theo cohort.';
    } else if (kpi.metric === 'cost_per_event') {
      proposedAction = `Giữ ngân sách ở nhóm/zone tạo ${eventLabel} hiệu quả và giảm từng bước 10–15% ở nhóm có chi phí cao; xác nhận bằng holdout.`;
      expectedMovement = `Đưa ${kpi.label} từ ${kpi.actual ?? 'N/A'} VND về không quá ${kpi.target} VND.`;
      guardrail = 'Không giảm volume của KPI count liên quan quá 10% trong cửa sổ đánh giá.';
    } else {
      proposedAction = `Ưu tiên thử nghiệm creative–audience tại ${topZone?.zoneId || 'zone đang dẫn đầu'} và xử lý điểm rơi funnel trước khi scale.`;
      expectedMovement = `Thu hẹp khoảng cách ${Math.abs(Number(kpi.gap) || 0)} cho ${kpi.label}.`;
      guardrail = 'Chỉ scale khi cost-per-event và chất lượng bước kế tiếp không xấu đi.';
    }
    actions.push({
      id: `action_${kpi.id}`,
      priority: kpi.status === 'bad' ? 'high' : 'medium',
      status: kpi.status,
      objective: measurementSpec.objective,
      problem: `${kpi.label}: thực tế ${kpi.actual ?? 'N/A'} ${kpi.unit}, mục tiêu ${kpi.operator} ${kpi.target} ${kpi.unit}.`,
      evidenceIds: ['kpi_scorecard', 'business_funnel', ...(topZone ? ['top_zone_ctr'] : [])],
      affectedScope: eventId || 'campaign',
      proposedAction,
      expectedMovement,
      guardrail,
      confidence: kpi.source === 'brief' ? 'high' : 'medium',
      nextReviewWindow: kpi.windowDays ? `${kpi.windowDays} ngày` : '3–7 ngày sau thay đổi',
    });
  }
  if (!actions.length && topZone) {
    actions.push({
      id: 'action_preserve_winner', priority: 'low', status: 'good',
      objective: measurementSpec.objective,
      problem: 'Các KPI có mục tiêu đều đang đạt trong kỳ báo cáo.',
      evidenceIds: ['kpi_scorecard', 'top_zone_ctr'], affectedScope: topZone.zoneId,
      proposedAction: `Giữ cấu hình thắng tại ${topZone.zoneId} và dùng tối đa 10% ngân sách cho thử nghiệm có kiểm soát.`,
      expectedMovement: 'Duy trì KPI trong khi tìm thêm tăng trưởng.',
      guardrail: 'Dừng thử nghiệm nếu KPI chính giảm quá 10%.',
      confidence: 'medium', nextReviewWindow: '7 ngày',
    });
  }
  return actions.slice(0, 5);
}

function buildV2MetricDefinitions(measurementSpec) {
  const definitions = { ...METRIC_DEFINITIONS };
  for (const event of measurementSpec.outcomeGraph?.events || []) {
    definitions[event.id] = {
      label: event.label, unit: 'count', formula: `sum(outcomes.${event.id})`,
    };
  }
  for (const kpi of measurementSpec.kpis || []) {
    if (kpi.metric === 'cost_per_event') {
      definitions[kpi.id] = {
        label: kpi.label, unit: 'VND', formula: `spend / outcomes.${kpi.eventId}`,
      };
    } else if (kpi.metric === 'event_rate') {
      definitions[kpi.id] = {
        label: kpi.label, unit: 'percent',
        formula: `outcomes.${kpi.numeratorEvent} / outcomes.${kpi.denominatorEvent} * 100`,
      };
    }
  }
  return definitions;
}

function buildReportContractV2(campaign, records, measurementSpec) {
  const dates = records.map(row => String(row.date || '')).filter(Boolean).sort();
  const timeframe = { start: dates[0] || campaign.startDate || null, end: dates.at(-1) || campaign.endDate || null };
  const totals = aggregateOutcomes(records, measurementSpec);
  const byZoneRows = new Map();
  for (const row of records) {
    const id = String(row.placementId || 'unknown');
    if (!byZoneRows.has(id)) byZoneRows.set(id, []);
    byZoneRows.get(id).push(row);
  }
  const zones = [...byZoneRows.entries()].map(([zoneId, rows]) => ({
    zoneId, ...aggregateOutcomes(rows, measurementSpec),
  }));
  const bestCtr = zones.filter(item => item.impressions > 0).sort((a, b) => b.ctr - a.ctr)[0] || null;
  const bestCpm = zones.filter(item => item.impressions > 0).sort((a, b) => a.cpm - b.cpm)[0] || null;
  const uniqueDates = [...new Set(dates)];
  const midpoint = Math.ceil(uniqueDates.length / 2);
  const firstDates = new Set(uniqueDates.slice(0, midpoint));
  const first = aggregateOutcomes(records.filter(row => firstDates.has(String(row.date || ''))), measurementSpec);
  const second = aggregateOutcomes(records.filter(row => !firstDates.has(String(row.date || ''))), measurementSpec);
  const kpiScorecard = evaluateKpis(measurementSpec, totals);
  const performanceStatus = overallPerformance(kpiScorecard);
  const actions = buildActions(kpiScorecard, measurementSpec, zones);
  const funnel = (measurementSpec.outcomeGraph?.events || []).map(item => ({
    eventId: item.id, label: item.label, value: totals.outcomes[item.id] || 0,
  }));
  const findings = [
    finding('campaign_totals', 'campaign', totals, 'Computed campaign totals for the complete report timeframe.'),
    finding('period_comparison', 'campaign', { first_period: first, second_period: second }, 'First-half and second-half comparison; no causal claim.'),
    finding('business_funnel', 'campaign', { events: funnel }, 'Ordered business outcomes defined by the approved measurement specification.'),
    finding('kpi_scorecard', 'campaign', { kpis: kpiScorecard }, 'Mechanical comparison of observed values with brief targets.'),
    finding('performance_status', 'campaign', performanceStatus, 'Worst material KPI state determines report attention level.'),
  ];
  if (bestCtr) findings.push(finding('top_zone_ctr', bestCtr.zoneId, bestCtr, 'Highest observed CTR among zones with delivery.', 'medium'));
  if (bestCpm) findings.push(finding('lowest_zone_cpm', bestCpm.zoneId, bestCpm, 'Lowest observed CPM among zones with delivery.', 'medium'));
  return {
    contractVersion: 'report-evidence-v2',
    source: 'scenario_simulation',
    campaignId: campaign.campaignId,
    inputHash: campaign.inputHash || measurementSpec.assumptions?.inputHash || null,
    objective: campaign.objective,
    timeframe,
    measurementSpec,
    metricDefinitions: buildV2MetricDefinitions(measurementSpec),
    findings,
    kpiScorecard,
    performanceStatus,
    businessFunnel: funnel,
    actions,
    limitations: [
      'Scenario facts estimate a coherent campaign outcome for decision testing; they are not ad-server delivery logs.',
      'Lagged outcomes are attributed to the originating campaign cohort date and evaluated within the KPI window.',
      'Observed association does not establish causality.',
      'Summed daily reach is not campaign unique reach across the full timeframe.',
      'Actions require operator review and a controlled measurement window before scaling.',
    ],
  };
}

function buildReportContract(campaign, records, measurementSpec) {
  if (measurementSpec?.version === 'measurement-spec-v2') {
    return buildReportContractV2(campaign, records, measurementSpec);
  }
  return buildLegacyReportContract(campaign, records);
}

function validateAnalysisResult(result, expectedQuestions, contract) {
  if (!result || typeof result !== 'object' || typeof result.overall !== 'string') {
    throw new Error('report analysis must contain an overall string');
  }
  const byId = new Map((result.questions || []).map(item => [item.id, item]));
  const findingIds = new Set(contract.findings.map(item => item.id));
  const metricDefinitions = contract.metricDefinitions || METRIC_DEFINITIONS;
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
          if (!metric.metricId || !metricDefinitions[metric.metricId]) {
            throw new Error(`report analysis invented metric: ${metric.metricId || metric.label || 'unknown'}`);
          }
        }
      }
    }
  }
  return result;
}

module.exports = {
  METRIC_DEFINITIONS,
  aggregate,
  buildReportContract,
  buildReportContractV2,
  evaluateKpis,
  statusFor,
  validateAnalysisResult,
};
