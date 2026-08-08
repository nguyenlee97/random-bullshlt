/**
 * reportGenerator.js — OpenAI-powered synthetic analytics data generator
 *
 * Generates 14-day synthetic performance data for each ad zone in a campaign,
 * then generates pre-built analysis Q&A for each of the 6 report types.
 *
 * Output:
 *   - analytics_records: 14 records × N zones (same 13-field schema)
 *   - report_analyses: 6 documents with pre-generated Q&A
 */
const AnalyticsRecord = require('../models/AnalyticsRecord');
const ReportAnalysis = require('../models/ReportAnalysis');
const { buildReportContract, validateAnalysisResult } = require('../lib/reportContract');
const { normalizeReportInput, buildMeasurementSpec } = require('../lib/reportMeasurement');
const { simulateReportFacts } = require('../lib/reportSyntheticData');

const OPENAI_API_KEY = process.env.OPENAI_API_KEY || '';
// Report generation is a fixed specialist. It is independent of the campaign
// conversation engine and cannot drift to the GreenNode model selection.
const OPENAI_MODEL = 'gpt-5.4-mini';
const OPENAI_URL = 'https://api.openai.com/v1/chat/completions';

// ─── Report types ────────────────────────────────────────────────────────────
const REPORT_TYPES = [
  'daily_ops', 'awareness', 'consideration', 'conversion', 'retention', 'executive',
];

// ─── Predefined questions per report type ────────────────────────────────────
const QUESTIONS_MAP = {
  daily_ops: [
    { id: 'op_q1', question: 'Tổng quan hiệu suất chiến dịch', category: 'performance' },
    { id: 'op_q2', question: 'So sánh hiệu suất giữa các ad zone', category: 'comparison' },
    { id: 'op_q3', question: 'Phân tích xu hướng CTR theo thời gian', category: 'trend' },
    { id: 'op_q4', question: 'Đánh giá hiệu quả chi tiêu', category: 'performance' },
    { id: 'op_q5', question: 'Top zone có hiệu suất tốt nhất', category: 'comparison' },
    { id: 'op_q6', question: 'Gợi ý tối ưu chiến dịch', category: 'optimization' },
  ],
  awareness: [
    { id: 'aw_q1', question: 'Phân tích Reach & Frequency', category: 'performance' },
    { id: 'aw_q2', question: 'Đánh giá Viewability theo zone', category: 'comparison' },
    { id: 'aw_q3', question: 'So sánh hiệu quả CPM giữa các zone', category: 'comparison' },
    { id: 'aw_q4', question: 'Phân tích Video completion rate', category: 'performance' },
    { id: 'aw_q5', question: 'Đánh giá mức độ phủ sóng thương hiệu', category: 'performance' },
    { id: 'aw_q6', question: 'Gợi ý tối ưu nhận diện thương hiệu', category: 'optimization' },
  ],
  consideration: [
    { id: 'co_q1', question: 'Phân tích CTR theo zone', category: 'performance' },
    { id: 'co_q2', question: 'So sánh CTR vs CPM', category: 'comparison' },
    { id: 'co_q3', question: 'Phân tích click volume trend', category: 'trend' },
    { id: 'co_q4', question: 'CTR theo ad format (banner vs skin)', category: 'comparison' },
    { id: 'co_q5', question: 'Top zone engagement', category: 'comparison' },
    { id: 'co_q6', question: 'Gợi ý tăng cường tương tác', category: 'optimization' },
  ],
  conversion: [
    { id: 'cv_q1', question: 'Phân tích tỷ lệ chuyển đổi theo channel', category: 'performance' },
    { id: 'cv_q2', question: 'Đánh giá CPA theo placement', category: 'comparison' },
    { id: 'cv_q3', question: 'So sánh Spend vs Conversions', category: 'comparison' },
    { id: 'cv_q4', question: 'Conversion funnel analysis', category: 'performance' },
    { id: 'cv_q5', question: 'Top converting zones', category: 'comparison' },
    { id: 'cv_q6', question: 'Gợi ý tối ưu chuyển đổi', category: 'optimization' },
  ],
  retention: [
    { id: 'rt_q1', question: 'Đánh giá tần suất tiếp cận theo zone', category: 'performance' },
    { id: 'rt_q2', question: 'CTR decay & creative fatigue analysis', category: 'trend' },
    { id: 'rt_q3', question: 'Week-over-week reach analysis', category: 'trend' },
    { id: 'rt_q4', question: 'Audience saturation analysis', category: 'performance' },
    { id: 'rt_q5', question: 'Gợi ý chống bão hòa quảng cáo', category: 'optimization' },
    { id: 'rt_q6', question: 'Chiến lược retention & re-engagement', category: 'optimization' },
  ],
  executive: [
    { id: 'ex_q1', question: 'Tổng quan sức khỏe chiến dịch', category: 'performance' },
    { id: 'ex_q2', question: 'Phân tích pacing ngân sách', category: 'performance' },
    { id: 'ex_q3', question: 'So sánh KPI kỳ đầu vs kỳ sau', category: 'comparison' },
    { id: 'ex_q4', question: 'Phân bổ ngân sách theo channel', category: 'comparison' },
    { id: 'ex_q5', question: 'Smart recommendations', category: 'optimization' },
    { id: 'ex_q6', question: 'Tổng hợp & đề xuất chiến lược', category: 'optimization' },
  ],
};

function questionsForReport(reportType, contract) {
  if (contract?.contractVersion !== 'report-evidence-v2') return QUESTIONS_MAP[reportType] || [];
  const events = contract.businessFunnel || [];
  const first = events[0]?.label || 'conversion đầu phễu';
  const last = events.at(-1)?.label || 'outcome chính';
  const objective = contract.objective;
  const overview = [
    { id: 'op_q1', question: 'Sức khỏe chiến dịch so với KPI trong brief đang ở mức Good, Watch hay Bad?', category: 'performance' },
    { id: 'op_q2', question: 'Thay đổi giữa hai nửa kỳ báo cáo nào cần chú ý nhất?', category: 'trend' },
    { id: 'op_q3', question: 'Zone nào nên giữ, thử nghiệm thêm hoặc giảm phân bổ?', category: 'comparison' },
    { id: 'op_q4', question: 'Các action ưu tiên, guardrail và thời điểm đánh giá lại là gì?', category: 'optimization' },
  ];
  if (reportType === 'daily_ops' || reportType === 'executive') return overview;
  if (reportType !== objective) return QUESTIONS_MAP[reportType] || [];
  const prefix = { awareness: 'aw', consideration: 'co', conversion: 'cv', retention: 'rt' }[reportType] || 'obj';
  const objectiveQuestions = {
    awareness: [
      `Quy mô phân phối, viewability và ${last} có đạt mục tiêu Awareness không?`,
      'Zone nào cân bằng tốt nhất giữa impressions, CPM và chất lượng hiển thị?',
      'Xu hướng nào đang tạo rủi ro fatigue hoặc giảm chất lượng nhận diện?',
      'Action Awareness nào nên ưu tiên và cần guardrail gì?',
    ],
    consideration: [
      `Luồng ${first} đến ${last} đang tạo tín hiệu cân nhắc như thế nào?`,
      'Zone nào tạo engagement hiệu quả theo CTR và cost-per-event?',
      'Tín hiệu nào cho thấy creative hoặc audience cần thử nghiệm lại?',
      'Action Consideration nào có evidence mạnh nhất và đo lại khi nào?',
    ],
    conversion: [
      `Funnel từ ${first} đến ${last} đang ở đâu so với KPI trong brief?`,
      `Chi phí và tỷ lệ chuyển bước đến ${last} đang Good, Watch hay Bad?`,
      `Zone nào tạo ${first} hiệu quả nhưng mất nhiều nhất ở bước business outcome?`,
      `Action nào nên ưu tiên để tăng ${last} mà không làm xấu cost-per-outcome?`,
    ],
    retention: [
      `Tín hiệu delivery lặp lại và ${last} có đạt KPI Retention không?`,
      `Zone nào duy trì ${first} và ${last} ổn định nhất?`,
      'Xu hướng nào cho thấy saturation, fatigue hoặc suy giảm re-engagement?',
      'Nên thử creative, audience hay frequency theo guardrail nào?',
    ],
  }[reportType] || [];
  return objectiveQuestions.map((question, index) => ({
    id: `${prefix}_q${index + 1}`, question,
    category: index === 3 ? 'optimization' : index === 2 ? 'trend' : 'performance',
  }));
}

function formatContractValue(value, unit) {
  if (!Number.isFinite(Number(value))) return 'N/A';
  if (unit === 'VND') return `${Math.round(Number(value)).toLocaleString('vi-VN')} VND`;
  if (unit === 'percent') return `${Number(value).toFixed(2)}%`;
  return Math.round(Number(value)).toLocaleString('vi-VN');
}

function buildEvidenceAnalysis(input, dataContract, reportType, questions) {
  const status = dataContract.performanceStatus || { status: 'watch', summary: 'Chưa đủ KPI để kết luận.' };
  const funnel = dataContract.businessFunnel || [];
  const funnelText = funnel.length
    ? funnel.map(item => `${item.label}: ${formatContractValue(item.value, 'count')}`).join(' → ')
    : 'Chưa có business outcome funnel.';
  const metricItems = (dataContract.kpiScorecard || []).slice(0, 4).map(kpi => ({
    metricId: kpi.metric === 'event_count' ? kpi.eventId
      : kpi.metric === 'media_metric' ? kpi.metricId : kpi.id,
    label: kpi.label,
    value: formatContractValue(kpi.actual, kpi.unit),
    trend: 'stable',
    delta: kpi.gap === null ? 'N/A' : formatContractValue(kpi.gap, kpi.unit),
    timeframe: `${dataContract.timeframe?.start}..${dataContract.timeframe?.end}`,
    source: dataContract.source,
  }));
  const actionItems = (dataContract.actions || []).slice(0, 3).map(action => ({
    priority: action.priority,
    text: `${action.proposedAction} Guardrail: ${action.guardrail} Đánh giá lại: ${action.nextReviewWindow}.`,
    actionId: action.id,
  }));
  const findingIds = (dataContract.findings || []).map(item => item.id);
  return {
    overall: `${status.summary} ${funnelText}`,
    questions: questions.map(question => ({
      id: question.id,
      findingIds: findingIds.filter(id => [
        'campaign_totals', 'period_comparison', 'business_funnel', 'kpi_scorecard',
        'performance_status', 'top_zone_ctr', 'lowest_zone_cpm',
      ].includes(id)),
      answer: {
        sections: [
          {
            type: 'summary',
            text: `${status.summary} Với ${input.brand}, dữ liệu cho thấy ${funnelText}`,
          },
          ...(metricItems.length ? [{ type: 'metrics', items: metricItems }] : []),
          {
            type: 'insight', level: status.status,
            text: `Mức ${status.status.toUpperCase()} được tính trực tiếp từ KPI trong brief; đây không phải đánh giá tự do của mô hình.`,
          },
          ...(actionItems.length ? [{ type: 'recommendation', items: actionItems }] : []),
          {
            type: 'limitation',
            text: 'Chỉ áp dụng action sau khi kiểm tra guardrail trong cửa sổ đánh giá đã nêu.',
          },
        ],
      },
    })),
    analysisProvenance: {
      provider: 'deterministic_fallback', model: 'none',
      reason: 'model_unavailable_or_invalid', reportType,
    },
  };
}

function normalizeModelSections(value) {
  if (Array.isArray(value)) return value.filter(item => item && typeof item === 'object');
  if (!value || typeof value !== 'object') return [];
  return Object.entries(value).flatMap(([type, content]) => {
    if (content && typeof content === 'object' && !Array.isArray(content)) {
      return [{ type: content.type || type, ...content }];
    }
    if (type === 'metrics' && Array.isArray(content)) return [{ type, items: content }];
    if (type === 'recommendation' && Array.isArray(content)) {
      return [{
        type,
        items: content.map(item => (typeof item === 'string'
          ? { priority: 'medium', text: item } : item)).filter(Boolean),
      }];
    }
    if (typeof content === 'string') return [{ type, text: content }];
    return [];
  });
}

function canonicalMetricItem(item, question, dataContract) {
  const metricId = item?.metricId;
  const definition = dataContract.metricDefinitions?.[metricId];
  if (!metricId || !definition) return null;
  const kpis = dataContract.kpiScorecard || [];
  const kpi = kpis.find(candidate => (
    candidate.id === metricId || candidate.metricId === metricId
    || candidate.eventId === metricId || candidate.numeratorEvent === metricId
  ));
  const funnel = (dataContract.businessFunnel || []).find(candidate => candidate.eventId === metricId);
  const findingIds = new Set(question.findingIds || []);
  const zoneFinding = findingIds.has('top_zone_ctr')
    ? dataContract.findings?.find(candidate => candidate.id === 'top_zone_ctr') : null;
  const outcomeZoneFinding = findingIds.has('outcome_zone_efficiency')
    ? dataContract.findings?.find(candidate => candidate.id === 'outcome_zone_efficiency') : null;
  const outcomeZones = outcomeZoneFinding?.metrics?.zones || [];
  const formulaEventId = String(definition.formula || '').match(/outcomes\.([a-z0-9_]+)/i)?.[1];
  let referencedZone = outcomeZones.find(zone => (
    item.scopeId === zone.zoneId || String(item.label || '').includes(zone.zoneId)
  ));
  if (!referencedZone && /zone/i.test(String(item.label || ''))) {
    if (outcomeZones.some(zone => Number.isFinite(Number(zone.outcomes?.[metricId])))) {
      referencedZone = [...outcomeZones].sort((a, b) => (
        Number(b.outcomes?.[metricId] || 0) - Number(a.outcomes?.[metricId] || 0)
      ))[0];
    } else if (formulaEventId) {
      referencedZone = [...outcomeZones].filter(zone => (
        Number.isFinite(Number(zone.costPerOutcome?.[formulaEventId]))
      )).sort((a, b) => (
        Number(a.costPerOutcome[formulaEventId]) - Number(b.costPerOutcome[formulaEventId])
      ))[0];
    }
  }
  const totals = dataContract.findings?.find(candidate => candidate.id === 'campaign_totals')?.metrics || {};
  let actual = kpi?.actual;
  if (funnel) actual = funnel.value;
  if (referencedZone && Number.isFinite(Number(referencedZone.outcomes?.[metricId]))) {
    actual = referencedZone.outcomes[metricId];
  } else if (referencedZone) {
    if (formulaEventId && Number.isFinite(Number(referencedZone.costPerOutcome?.[formulaEventId]))) {
      actual = referencedZone.costPerOutcome[formulaEventId];
    }
  } else if (zoneFinding?.metrics && Number.isFinite(Number(zoneFinding.metrics[metricId]))) {
    actual = zoneFinding.metrics[metricId];
  } else if (!Number.isFinite(Number(actual)) && Number.isFinite(Number(totals[metricId]))) {
    actual = totals[metricId];
  }
  if (!Number.isFinite(Number(actual))) return null;
  const groundedGap = referencedZone && kpi
    ? Number(actual) - Number(kpi.target)
    : kpi?.gap;
  const delta = kpi && Number.isFinite(Number(groundedGap))
    ? `${formatContractValue(groundedGap, kpi.unit)} so với mục tiêu`
    : 'N/A';
  return {
    metricId,
    label: referencedZone ? `${definition.label} · ${referencedZone.zoneId}` : definition.label,
    value: formatContractValue(actual, definition.unit),
    trend: 'stable',
    delta,
    timeframe: `${dataContract.timeframe?.start}..${dataContract.timeframe?.end}`,
    source: dataContract.source,
  };
}

function groundAnalysisResult(result, dataContract) {
  const status = dataContract.performanceStatus || {
    status: 'watch', summary: 'Chưa đủ KPI để kết luận.',
  };
  const fixedStatus = status.status;
  const fixedRecommendations = (dataContract.actions || []).map(action => ({
    priority: action.priority,
    text: `${action.proposedAction} Guardrail: ${action.guardrail} Đánh giá lại: ${action.nextReviewWindow}.`,
    actionId: action.id,
  }));

  // Status and recommended actions are mechanical evidence outputs. The model
  // may explain them, but it cannot soften BAD into WATCH or replace actions.
  result.overall = `Trạng thái tổng thể: ${fixedStatus.toUpperCase()}. ${status.summary}`;
  if (!Array.isArray(result.questions) && result.questions && typeof result.questions === 'object') {
    result.questions = Object.entries(result.questions).map(([id, item]) => ({
      id, ...(item && typeof item === 'object' ? item : {}),
    }));
  }
  if (!Array.isArray(result.questions)) result.questions = [];
  for (const item of result.questions) {
    if (!item.answer || typeof item.answer !== 'object') item.answer = {};
    const sections = normalizeModelSections(item.answer.sections);
    item.answer.sections = sections;
    for (const section of sections.filter(candidate => candidate.type === 'metrics')) {
      section.items = (Array.isArray(section.items) ? section.items : [])
        .map(metric => canonicalMetricItem(metric, item, dataContract))
        .filter(Boolean)
        .slice(0, 4);
    }
    let insight = sections.find(section => section.type === 'insight');
    if (!insight) {
      insight = { type: 'insight' };
      sections.push(insight);
    }
    insight.level = fixedStatus;
    insight.text = `${status.summary} Trạng thái ${fixedStatus.toUpperCase()} được tính trực tiếp từ KPI trong brief.`;

    let recommendation = sections.find(section => section.type === 'recommendation');
    if (!recommendation && fixedRecommendations.length) {
      recommendation = { type: 'recommendation', items: [] };
      sections.push(recommendation);
    }
    if (recommendation && fixedRecommendations.length) {
      recommendation.items = fixedRecommendations.slice(0, 3);
    }
  }
  return result;
}

// ─── OpenAI call helper ──────────────────────────────────────────────────────
function buildOpenAIRequestBody(model, messages, temperature, maxCompletionTokens) {
  const body = {
    model,
    messages,
    max_completion_tokens: maxCompletionTokens,
    response_format: { type: 'json_object' },
  };
  // GPT-5-family chat models reject non-default sampling parameters. Older
  // compatible models may still use the configured report temperature.
  if (!String(model).toLowerCase().startsWith('gpt-5')) {
    body.temperature = temperature;
  }
  return body;
}


async function callOpenAI(messages, { temperature = 0.7, max_completion_tokens = 8000 } = {}) {
  if (!OPENAI_API_KEY) throw new Error('OPENAI_API_KEY not set');
  console.log(`[openai] → model=${OPENAI_MODEL} max_completion_tokens=${max_completion_tokens} prompt_len=${JSON.stringify(messages).length}`);
  const res = await fetch(OPENAI_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${OPENAI_API_KEY}`,
    },
    body: JSON.stringify(buildOpenAIRequestBody(
      OPENAI_MODEL, messages, temperature, max_completion_tokens,
    )),
  });
  const raw = await res.text();
  if (!res.ok) {
    console.error(`[openai] ✗ HTTP ${res.status}: ${raw.slice(0, 500)}`);
    throw new Error(`OpenAI ${res.status}: ${raw.slice(0, 300)}`);
  }
  let data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    console.error(`[openai] ✗ JSON parse failed: ${raw.slice(0, 300)}`);
    throw new Error(`OpenAI response not valid JSON: ${raw.slice(0, 200)}`);
  }
  const usage = data.usage || {};
  const content = data.choices?.[0]?.message?.content || '{}';
  console.log(`[openai] ✓ tokens: prompt=${usage.prompt_tokens} completion=${usage.completion_tokens} total=${usage.total_tokens} | content_len=${content.length}`);
  console.log(`[openai] content_preview: ${content.slice(0, 200)}`);
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch (e) {
    console.error(`[openai] ✗ content JSON parse failed: ${content.slice(0, 300)}`);
    throw new Error(`OpenAI content not valid JSON: ${content.slice(0, 200)}`);
  }
  return parsed;
}

// Preserve the model's relative delivery shape while keeping newly generated
// reports inside the campaign budget. Scaling every delivery volume by the
// same factor keeps CPM, CTR, CPA, frequency, trends, and zone rankings stable.
function normalizeGeneratedRecordsToBudget(records, budget) {
  if (!Array.isArray(records) || records.length === 0) return [];

  const campaignBudget = Number(budget);
  const totalSpend = records.reduce((sum, row) => {
    const spend = Number(row?.spend);
    return sum + (Number.isFinite(spend) && spend > 0 ? spend : 0);
  }, 0);

  if (!Number.isFinite(campaignBudget) || campaignBudget <= 0
      || totalSpend <= campaignBudget || totalSpend <= 0) {
    return records;
  }

  const targetSpend = campaignBudget * 0.85;
  const scale = targetSpend / totalSpend;
  const scaleCount = value => {
    const numeric = Number(value);
    return Number.isFinite(numeric) && numeric > 0
      ? Math.round(numeric * scale)
      : 0;
  };
  const roundMetric = value => Math.round(value * 1000) / 1000;

  const normalized = records.map((row) => {
    const impressions = scaleCount(row.impressions);
    const clicks = scaleCount(row.clicks);
    const spend = scaleCount(row.spend);
    const reach = scaleCount(row.reach);
    const conversions = scaleCount(row.conversions);
    return {
      ...row,
      impressions,
      clicks,
      spend,
      reach,
      conversions,
      ctr: impressions > 0 ? roundMetric(clicks / impressions * 100) : 0,
      cpm: impressions > 0 ? roundMetric(spend / impressions * 1000) : 0,
    };
  });

  const normalizedSpend = normalized.reduce((sum, row) => sum + row.spend, 0);
  console.log(
    `[reportGen] Normalized generated delivery to budget: `
    + `${Math.round(totalSpend)} -> ${normalizedSpend} VND (scale=${scale.toFixed(4)})`
  );
  return normalized;
}

// ─── Generate synthetic analytics records ────────────────────────────────────
async function generateRecords(campaign) {
  const input = campaign.contractVersion === 'report-input-v2'
    ? campaign : normalizeReportInput(campaign);
  const measurementSpec = buildMeasurementSpec(input);
  return simulateReportFacts(input, measurementSpec);
}

// ─── Generate analysis for one report type ───────────────────────────────────
async function generateAnalysis(campaign, records, reportType) {
  const input = campaign.contractVersion === 'report-input-v2'
    ? campaign : normalizeReportInput(campaign);
  const measurementSpec = buildMeasurementSpec(input);
  const dataContract = buildReportContract(input, records, measurementSpec);
  const questions = questionsForReport(reportType, dataContract);
  const questionList = questions.map(q => `- ${q.id}: "${q.question}" (${q.category})`).join('\n');

  // Summarize records for context
  const totalImp = records.reduce((s, r) => s + (r.impressions || 0), 0);
  const totalClk = records.reduce((s, r) => s + (r.clicks || 0), 0);
  const totalSpend = records.reduce((s, r) => s + (r.spend || 0), 0);
  const totalConv = records.reduce((s, r) => s + (r.conversions || 0), 0);
  const avgCTR = totalImp > 0 ? (totalClk / totalImp * 100).toFixed(3) : 0;
  const avgVI = records.length > 0 ? (records.reduce((s, r) => s + (r.vi || 0), 0) / records.length).toFixed(1) : 0;

  // Per-zone summary
  const zoneMap = {};
  records.forEach(r => {
    if (!zoneMap[r.placementId]) zoneMap[r.placementId] = { imp: 0, clk: 0, spend: 0, conv: 0, vi: 0, n: 0 };
    const z = zoneMap[r.placementId];
    z.imp += r.impressions || 0;
    z.clk += r.clicks || 0;
    z.spend += r.spend || 0;
    z.conv += r.conversions || 0;
    z.vi += r.vi || 0;
    z.n++;
  });
  const zoneSummary = Object.entries(zoneMap).map(([id, z]) =>
    `${id}: ${z.imp} imps, ${z.clk} clicks, CTR ${z.imp > 0 ? (z.clk / z.imp * 100).toFixed(2) : 0}%, Spend ${Math.round(z.spend / 1000000)}M, VI ${(z.vi / z.n).toFixed(1)}%`
  ).join('\n');

  const prompt = `You are an expert digital advertising analyst. Analyze this campaign data and answer predefined questions.

CAMPAIGN: ${input.brand} | Objective: ${input.objective} | Budget: ${Math.round(input.budget / 1000000)}M VND
PERIOD: ${input.startDate} to ${input.endDate} (${input.durationDays} days) | Zones: ${Object.keys(zoneMap).length}

TOTALS: ${totalImp.toLocaleString()} impressions | ${totalClk.toLocaleString()} clicks | CTR ${avgCTR}% | Spend ${Math.round(totalSpend / 1000000)}M VND | ${totalConv} conversions | Avg VI ${avgVI}%

PER-ZONE:
${zoneSummary}

REPORT TYPE: ${reportType.replace('_', ' ').toUpperCase()}

AUTHORITATIVE EVIDENCE CONTRACT (the only allowed source of numbers and claims):
${JSON.stringify(dataContract)}

QUESTIONS TO ANSWER:
${questionList}

For each question, provide a structured analysis. Output JSON:
{
  "overall": "2-3 sentence overall summary for this report type in Vietnamese",
  "questions": [
    {
      "id": "question_id",
      "findingIds": ["campaign_totals"],
      "answer": {
        "sections": [
          { "type": "summary", "text": "1-2 sentence summary in Vietnamese" },
          { "type": "metrics", "items": [
            { "metricId": "ctr", "label": "Metric Name", "value": "formatted value", "trend": "up|down|stable", "delta": "+X%", "timeframe": "YYYY-MM-DD..YYYY-MM-DD", "source": "synthetic_showcase" }
          ]},
          { "type": "insight", "level": "good|watch|bad", "text": "Explain the fixed performance status from evidence in Vietnamese" },
          { "type": "recommendation", "items": [
            { "priority": "high|medium|low", "text": "Action recommendation in Vietnamese" }
          ]}
        ]
      }
    }
  ]
}

RULES:
- All text in Vietnamese
- Use specific numbers from the data
- Use only metric IDs and finding IDs present in AUTHORITATIVE EVIDENCE CONTRACT
- Never present summed_daily_reach as unique campaign reach
- The KPI status and actions in the contract are fixed facts: explain them, never override or replace them
- Do not put internal provenance labels in the overall summary
- Do not claim causality, guaranteed results, or that a recommendation was applied
- If evidence is unavailable, say it is unavailable; never construct a substitute metric
- Be professional and actionable
- Each answer should have 2-4 sections
- Include at least one recommendation per answer`;

  let result;
  try {
    result = await callOpenAI([
      { role: 'system', content: 'You are a Vietnamese digital advertising analyst. Output ONLY valid JSON. Be specific, data-driven, and professional.' },
      { role: 'user', content: prompt },
    ], { temperature: 0.6, max_completion_tokens: 8000 });

    groundAnalysisResult(result, dataContract);
    validateAnalysisResult(result, questions, dataContract);
    result.analysisProvenance = { provider: 'openai', model: OPENAI_MODEL, reportType };
  } catch (error) {
    if (dataContract.contractVersion !== 'report-evidence-v2') throw error;
    console.warn(`[reportGen] Report Specialist fallback for ${reportType}: ${error.message}`);
    result = buildEvidenceAnalysis(input, dataContract, reportType, questions);
    validateAnalysisResult(result, questions, dataContract);
  }
  return { ...result, dataContract };
}

// ─── Main: generate all reports for a campaign ───────────────────────────────
async function generateReports(campaign) {
  const input = campaign.contractVersion === 'report-input-v2'
    ? campaign : normalizeReportInput(campaign);
  const { campaignId } = input;
  console.log(`[reportGen] Starting generation for campaign ${campaignId}`);

  // Check if records already exist AND have real data
  const existing = await AnalyticsRecord.countDocuments({ campaignId });
  const existingWithData = existing > 0
    ? await AnalyticsRecord.countDocuments({ campaignId, impressions: { $gt: 0 } })
    : 0;
  const existingForInput = existing > 0
    ? await AnalyticsRecord.countDocuments({ campaignId, inputHash: input.inputHash })
    : 0;

  if (existing > 0 && (existingWithData === 0 || existingForInput !== existing)) {
    console.log(`[reportGen] Replacing ${existing} stale/legacy records for input ${input.inputHash.slice(0, 12)}`);
    await AnalyticsRecord.deleteMany({ campaignId });
  }

  const shouldGenerate = existing === 0 || existingWithData === 0 || existingForInput !== existing;
  if (!shouldGenerate) {
    console.log(`[reportGen] ${existing} records (${existingWithData} with data) already exist for ${campaignId} — reusing`);
  }

  // Step 1: Generate synthetic records (if not already present with real data)
  let records;
  if (shouldGenerate) {
    try {
      records = await generateRecords(input);
      console.log(`[reportGen] OpenAI returned ${records.length} records`);
      if (records.length > 0) {
        await AnalyticsRecord.insertMany(records);
        console.log(`[reportGen] Inserted ${records.length} analytics records for ${campaignId}`);
      } else {
        console.error(`[reportGen] ⚠️  OpenAI returned 0 records — check prompt or API response`);
      }
    } catch (err) {
      console.error(`[reportGen] Record generation failed:`, err.message);
      // Mark all report types as error
      for (const rt of REPORT_TYPES) {
        await ReportAnalysis.findOneAndUpdate(
          { campaignId, reportType: rt },
          { $set: { status: 'error', error: err.message } },
          { upsert: true }
        );
      }
      throw err;
    }
  } else {
    records = await AnalyticsRecord.find({ campaignId }).lean();
    console.log(`[reportGen] Loaded ${records.length} existing records for ${campaignId}`);
  }

  // Step 2: Generate analyses for each report type (parallel)
  const analysisPromises = REPORT_TYPES.map(async (reportType) => {
    // Create placeholder
    await ReportAnalysis.findOneAndUpdate(
      { campaignId, reportType },
      { $set: { status: 'generating' } },
      { upsert: true }
    );

    try {
      const result = await generateAnalysis(input, records, reportType);
      const questions = questionsForReport(reportType, result.dataContract).map((q) => {
        const answered = (result.questions || []).find(a => a.id === q.id);
        return {
          ...q,
          findingIds: answered?.findingIds || [],
          answer: answered?.answer || { sections: [{ type: 'summary', text: 'Chưa có phân tích cho câu hỏi này.' }] },
        };
      });

      await ReportAnalysis.findOneAndUpdate(
        { campaignId, reportType },
        {
          $set: {
            status: 'ready',
            overall: result.overall || '',
            questions,
            dataContract: result.dataContract,
            inputHash: input.inputHash,
            schemaVersion: result.dataContract.contractVersion,
            performanceStatus: result.dataContract.performanceStatus,
            actions: result.dataContract.actions,
            provenance: {
              provider: result.analysisProvenance?.provider || 'openai',
              model: result.analysisProvenance?.model || OPENAI_MODEL,
              schema: 'report-evidence-v2', source: 'scenario_simulation',
              inputHash: input.inputHash,
              fallbackReason: result.analysisProvenance?.reason || null,
            },
            generatedAt: new Date(),
            error: '',
          },
        }
      );
      console.log(`[reportGen] Analysis ready: ${reportType} for ${campaignId}`);
    } catch (err) {
      console.error(`[reportGen] Analysis failed for ${reportType}:`, err.message);
      await ReportAnalysis.findOneAndUpdate(
        { campaignId, reportType },
        { $set: { status: 'error', error: err.message } }
      );
    }
  });

  await Promise.allSettled(analysisPromises);
  console.log(`[reportGen] All analyses complete for ${campaignId}`);
}

// ─── Get generation status ───────────────────────────────────────────────────
async function getReportStatus(campaignId) {
  const docs = await ReportAnalysis.find({ campaignId }).lean();
  const status = {};
  for (const rt of REPORT_TYPES) {
    const doc = docs.find(d => d.reportType === rt);
    status[rt] = doc?.status || 'pending';
  }
  const ready = Object.values(status).filter(s => s === 'ready').length;
  const errors = Object.values(status).filter(s => s === 'error').length;
  const contractReady = docs.filter(doc => (
    doc?.status === 'ready' && doc?.dataContract?.contractVersion === 'report-evidence-v2'
  )).length;
  return { campaignId, total: REPORT_TYPES.length, ready, errors, contractReady, types: status };
}

module.exports = {
  generateReports, getReportStatus, REPORT_TYPES, QUESTIONS_MAP,
  buildOpenAIRequestBody, generateAnalysis, normalizeGeneratedRecordsToBudget,
  generateRecords, questionsForReport, buildEvidenceAnalysis, groundAnalysisResult,
};
