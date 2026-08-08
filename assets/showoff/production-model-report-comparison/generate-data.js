'use strict';

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..', '..');
const { normalizeReportInput, buildMeasurementSpec } = require(path.join(ROOT, 'backend/lib/reportMeasurement'));
const { simulateReportFacts } = require(path.join(ROOT, 'backend/lib/reportSyntheticData'));
const { buildReportContract, validateAnalysisResult } = require(path.join(ROOT, 'backend/lib/reportContract'));
const { questionsForReport, groundAnalysisResult } = require(path.join(ROOT, 'backend/services/reportGenerator'));

const AGENT_BASE = process.env.PRODUCTION_AGENT_URL || 'https://agent-api.pawgrammers.io.vn/api/agent';
const MODEL_LOCK = 'openai_gpt_5_4_mini';

function mocAnInput() {
  const measurementSpec = {
    version: 'measurement-spec-v2',
    objective: 'conversion',
    optimizationEvent: 'lead_or_subscription',
    primaryOutcome: 'subscribed',
    outcomeGraph: {
      events: [
        { id: 'lead_or_subscription', label: 'Lead hoặc đăng ký subscription', stage: 'conversion_intent', baseRate: 0.041 },
        { id: 'qualified_lead', label: 'Lead chất lượng', stage: 'qualified_lead', baseRate: 0.72 },
        { id: 'subscribed', label: 'Đăng ký gói giao sữa', stage: 'subscription', baseRate: 0.26 },
      ],
      transitions: [
        { from: 'lead_or_subscription', to: 'qualified_lead', expectedRate: 0.72 },
        { from: 'qualified_lead', to: 'subscribed', expectedRate: 0.26 },
      ],
    },
    kpis: [
      {
        id: 'count_lead_or_subscription', label: 'Lead hoặc đăng ký subscription',
        metric: 'event_count', eventId: 'lead_or_subscription', operator: '>=',
        target: 5000, unit: 'count', source: 'brief', sourceText: '~5.000 lead/đơn',
      },
      {
        id: 'target_click_conversion_rate', label: 'CVR click → lead/subscription',
        metric: 'media_metric', metricId: 'click_conversion_rate', operator: '>=',
        target: 4, unit: 'percent', source: 'brief', sourceText: 'CVR > 4%',
      },
      {
        id: 'cost_per_lead_or_subscription', label: 'CPL lead/subscription',
        metric: 'cost_per_event', eventId: 'lead_or_subscription', operator: '<=',
        target: 85000, unit: 'VND', source: 'brief', sourceText: 'CPL dưới 85k',
      },
    ],
    dimensions: ['date', 'placementId', 'channel', 'format'],
    attribution: { clickWindowDays: 7, viewWindowDays: 1, maxOutcomeLagDays: 30 },
    assumptions: {
      source: 'brief_and_objective_rules', deterministic: true,
      outcomeTimeBasis: 'cohort_origin_date',
      ambiguousVolumeKpi: '~5.000 lead/đơn được đo như tổng lead hoặc đăng ký subscription đầu phễu.',
    },
    measurementGaps: [{
      id: 'target_roas', label: 'ROAS', operator: '>', target: 2,
      status: 'not_evaluable',
      missingInputs: ['recognized_revenue', 'subscription_plan_value', 'refund_or_cancellation_value'],
      reason: 'Brief chưa cung cấp giá trị gói hoặc revenue được ghi nhận nên không tạo ROAS giả.',
    }],
  };

  return {
    campaignId: 'MOCAN-DAIRY-REPORT-V2',
    brand: 'MộcAn Dairy',
    objective: 'conversion',
    budget: 250_000_000,
    startDate: '2026-08-10',
    endDate: '2026-08-30',
    kpi: '~5.000 lead/đơn. CVR > 4%. CPL dưới 85.000 VND. ROAS > 2.0.',
    notes: 'Thu đăng ký gói giao sữa hằng tháng và lead nhận hộp dùng thử. Ưu tiên retargeting; mobile; tránh claim sức khỏe gây hiểu lầm.',
    geo: ['TP.HCM', 'Hà Nội', 'Đà Nẵng'],
    audience: ['Nữ 28–40 có con 2–10 tuổi', 'Nhân viên văn phòng 25–35 sống lành mạnh', 'Retarget landing/add-to-cart'],
    zones: [
      { id: 'zalo_lead_form_native', channel: 'Zalo', format: 'native_lead_form', cpm: 50_000, weight: 1.18 },
      { id: 'baomoi_dynamic_product_mobile', channel: 'BaoMoi', format: 'dynamic_product', cpm: 57_000, weight: 0.96 },
      { id: 'zalo_retargeting_mobile', channel: 'Zalo', format: 'retargeting_mobile', cpm: 46_000, weight: 1.24 },
    ],
    strategy: { selected: 'quality_first', frequency: 3.4 },
    forecast: { averageCpm: 50_000, frequency: 3.4 },
    measurementSpec,
    briefAssumptions: [
      'Brief chỉ nêu thời lượng 3 tuần; report dùng 10/08/2026–30/08/2026 để kiểm thử.',
      'KPI ~5.000 lead/đơn được diễn giải thành tổng lead hoặc đăng ký subscription đầu phễu.',
      'ROAS không được tính khi thiếu giá trị gói và recognized revenue.',
    ],
  };
}

function buildReport(raw) {
  const input = normalizeReportInput(raw);
  const measurementSpec = buildMeasurementSpec(input);
  const records = simulateReportFacts(input, measurementSpec);
  const contract = buildReportContract(input, records, measurementSpec);
  return { raw, input, measurementSpec, records, contract };
}

function aggregateRows(rows, key) {
  const map = new Map();
  for (const row of rows) {
    const id = row[key];
    if (!map.has(id)) map.set(id, {
      id, impressions: 0, clicks: 0, spend: 0, conversions: 0,
      reach: 0, viWeighted: 0, outcomes: {},
    });
    const item = map.get(id);
    item.impressions += row.impressions || 0;
    item.clicks += row.clicks || 0;
    item.spend += row.spend || 0;
    item.conversions += row.conversions || 0;
    item.reach += row.reach || 0;
    item.viWeighted += (row.vi || 0) * (row.impressions || 0);
    for (const [eventId, value] of Object.entries(row.outcomes || {})) {
      item.outcomes[eventId] = (item.outcomes[eventId] || 0) + value;
    }
  }
  return [...map.values()].map(item => ({
    ...item,
    ctr: item.impressions ? item.clicks / item.impressions * 100 : 0,
    cpm: item.impressions ? item.spend / item.impressions * 1000 : 0,
    viewability: item.impressions ? item.viWeighted / item.impressions : 0,
  })).sort((a, b) => String(a.id).localeCompare(String(b.id)));
}

function compactEvidence(report, questions) {
  const { contract } = report;
  const zones = aggregateRows(report.records, 'placementId').map(item => ({
    zoneId: item.id, ctr: Number(item.ctr.toFixed(3)), cpm: Math.round(item.cpm),
    spend: item.spend, outcomes: item.outcomes,
    costPerOutcome: Object.fromEntries(Object.entries(item.outcomes).map(([eventId, value]) => [
      eventId, value > 0 ? Math.round(item.spend / value) : null,
    ])),
  }));
  const questionEvidence = Object.fromEntries(questions.map((question, index) => [
    question.id,
    index === 0 ? {
      fixedStatus: contract.performanceStatus,
      funnel: contract.businessFunnel,
      countKpis: contract.kpiScorecard.filter(item => item.metric === 'event_count'),
    } : index === 1 ? {
      fixedStatus: contract.performanceStatus,
      kpis: contract.kpiScorecard,
    } : index === 2 ? {
      zones,
      instruction: 'So sánh cost-per-business-outcome; CTR/CPM chỉ là supporting media signals.',
    } : {
      fixedStatus: contract.performanceStatus,
      actions: contract.actions,
      measurementGaps: report.measurementSpec.measurementGaps || [],
    },
  ]));
  return {
    brand: report.input.brand,
    objective: report.input.objective,
    timeframe: contract.timeframe,
    budget: report.input.budget,
    performanceStatus: contract.performanceStatus,
    measurementGaps: report.measurementSpec.measurementGaps || [],
    limitations: contract.limitations.slice(0, 3),
    allowedFindingIds: contract.findings.map(item => item.id),
    allowedMetricIds: Object.keys(contract.metricDefinitions),
    questions,
    questionEvidence,
  };
}

function modelPrompt(report, questions) {
  const evidence = compactEvidence(report, questions);
  return `Chỉ trả về JSON hợp lệ, không markdown, không cập nhật campaign hoặc workspace.
Bạn là Report Specialist phân tích campaign bằng tiếng Việt. Facts và KPI status trong evidence là cố định; không được thay đổi hoặc tạo số liệu mới. Viết thật gọn vì evidence layer sẽ gắn status và action sau.

OUTPUT SCHEMA:
{"overall":"1 câu","questions":[{"id":"question_id","findingIds":["allowed_id"],"answer":{"sections":[{"type":"summary","text":"tối đa 80 từ"},{"type":"metrics","items":[{"metricId":"allowed_metric_id","label":"...","value":"...","trend":"up|down|stable","delta":"...","timeframe":"YYYY-MM-DD..YYYY-MM-DD","source":"scenario_simulation"}]}]}}]}

RULES:
- Trả đủ đúng các question id trong evidence, theo đúng thứ tự.
- Mỗi question chỉ dùng facts trong questionEvidence có cùng id.
- Chỉ dùng findingIds và metricIds được phép.
- Mỗi câu chỉ có summary và tối đa 2 metrics; không viết recommendation hoặc lặp toàn bộ funnel.
- Giải thích cụ thể theo funnel/KPI, không claim causal hoặc guaranteed outcome.
- Không tự tính ROAS nếu measurementGaps nói thiếu revenue.
- Status và action do evidence layer gắn sau, model không tự viết.

EVIDENCE:
${JSON.stringify(evidence)}`;
}

function parseModelJson(text) {
  const clean = String(text || '').trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  const start = clean.indexOf('{');
  const end = clean.lastIndexOf('}');
  if (start < 0 || end <= start) throw new Error('model did not return a JSON object');
  return JSON.parse(clean.slice(start, end + 1));
}

function cookieJar() {
  const values = new Map();
  return {
    capture(response) {
      const setCookies = response.headers.getSetCookie?.() || [];
      for (const value of setCookies) {
        const pair = value.split(';', 1)[0];
        const index = pair.indexOf('=');
        if (index > 0) values.set(pair.slice(0, index), pair.slice(index + 1));
      }
    },
    header() { return [...values.entries()].map(([key, value]) => `${key}=${value}`).join('; '); },
    get(name) { return values.get(name); },
  };
}

async function requestJson(url, options, jar) {
  const headers = { ...(options.headers || {}) };
  if (jar.header()) headers.Cookie = jar.header();
  const response = await fetch(url, { ...options, headers });
  jar.capture(response);
  const text = await response.text();
  if (!response.ok) throw new Error(`${response.status} ${url}: ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : {};
}

async function callProductionModel(report, reportType) {
  const questions = questionsForReport(reportType, report.contract);
  const prompt = modelPrompt(report, questions);
  if (prompt.length > 11_900) throw new Error(`model prompt exceeds production chat limit: ${prompt.length}`);
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const jar = cookieJar();
    let conversationId;
    try {
      await requestJson(`${AGENT_BASE}/auth/anonymous`, { method: 'POST' }, jar);
      const csrf = jar.get('aa_csrf');
      if (!csrf) throw new Error('production Agent did not issue CSRF cookie');
      const commonHeaders = { 'Content-Type': 'application/json; charset=utf-8', 'x-csrf-token': csrf };
      const created = await requestJson(`${AGENT_BASE}/conversations`, {
        method: 'POST', headers: commonHeaders,
        body: JSON.stringify({
          title: `${report.input.brand} Report v2 production verification`,
          experience_mode: 'guided', conversation_model: MODEL_LOCK,
        }),
      }, jar);
      conversationId = created.conversation_id;
      const answer = await requestJson(`${AGENT_BASE}/chat`, {
        method: 'POST', headers: commonHeaders,
        body: JSON.stringify({
          session_id: created.session_id, step: 0,
          experience_mode: 'guided', message: prompt,
        }),
      }, jar);
      if (answer.meta?.model !== 'gpt-5.4-mini') {
        throw new Error(`unexpected production model: ${answer.meta?.model || 'none'}`);
      }
      const rawAnalysis = parseModelJson(answer.text);
      const productAnalysis = groundAnalysisResult(structuredClone(rawAnalysis), report.contract);
      validateAnalysisResult(productAnalysis, questions, report.contract);
      return {
        rawAnalysis,
        productAnalysis,
        provenance: {
          provider: 'production_agent', model: answer.meta.model,
          tool: answer.meta.tool, conversationModel: created.conversation_model,
          validated: true, attempt, generatedAt: new Date().toISOString(),
        },
      };
    } catch (error) {
      lastError = error;
    } finally {
      if (conversationId) {
        try {
          await requestJson(`${AGENT_BASE}/conversations/${conversationId}`, {
            method: 'DELETE', headers: { 'x-csrf-token': jar.get('aa_csrf') },
          }, jar);
        } catch (_) { /* cleanup is best effort */ }
      }
    }
  }
  throw lastError;
}

function serializeReport(report, modelResult) {
  return {
    input: {
      campaignId: report.input.campaignId, brand: report.input.brand,
      objective: report.input.objective, budget: report.input.budget,
      startDate: report.input.startDate, endDate: report.input.endDate,
      durationDays: report.input.durationDays, geo: report.input.geo,
      briefAssumptions: report.raw.briefAssumptions || [],
    },
    measurementSpec: report.measurementSpec,
    contract: report.contract,
    daily: aggregateRows(report.records, 'date'),
    zones: aggregateRows(report.records, 'placementId'),
    recordCount: report.records.length,
    model: modelResult,
  };
}

async function main() {
  const voltRideRaw = JSON.parse(fs.readFileSync(
    path.join(ROOT, 'backend/tests/fixtures/voltride-report-v2.json'), 'utf8'
  ));
  const reports = [buildReport(voltRideRaw), buildReport(mocAnInput())];
  const results = [];
  for (const report of reports) {
    process.stderr.write(`Running production GPT-5.4-mini for ${report.input.brand}...\n`);
    const modelResult = await callProductionModel(report, report.input.objective);
    results.push(serializeReport(report, modelResult));
  }
  const output = {
    generatedAt: new Date().toISOString(),
    methodology: {
      facts: 'Report v2 deterministic scenario facts',
      analysis: 'Production Agent GPT-5.4-mini, grounded and validated locally',
      statusOwner: 'Evidence contract', actionOwner: 'Evidence contract',
    },
    reports: results,
  };
  fs.writeFileSync(path.join(__dirname, 'report-data.json'), `${JSON.stringify(output, null, 2)}\n`, 'utf8');
  process.stdout.write(JSON.stringify({
    generatedAt: output.generatedAt,
    reports: results.map(item => ({
      brand: item.input.brand, status: item.contract.performanceStatus,
      funnel: item.contract.businessFunnel,
      model: item.model.provenance,
    })),
  }, null, 2));
}

main().catch(error => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
