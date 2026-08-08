'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fixture = require('./fixtures/voltride-report-v2.json');
const { normalizeReportInput, buildMeasurementSpec } = require('../lib/reportMeasurement');
const { simulateReportFacts, validateReportFacts } = require('../lib/reportSyntheticData');
const { buildReportContract } = require('../lib/reportContract');
const {
  questionsForReport, buildEvidenceAnalysis, groundAnalysisResult,
} = require('../services/reportGenerator');

function buildVoltRide() {
  const input = normalizeReportInput(fixture);
  const measurement = buildMeasurementSpec(input);
  const rows = simulateReportFacts(input, measurement);
  const contract = buildReportContract(input, rows, measurement);
  return { input, measurement, rows, contract };
}

test('VoltRide report v2 uses the complete brief duration and business outcome graph', () => {
  const { input, measurement, rows } = buildVoltRide();
  assert.equal(input.durationDays, 35);
  assert.equal(rows.length, 35 * fixture.zones.length);
  assert.deepEqual(measurement.outcomeGraph.events.map(item => item.id), [
    'test_ride_registration', 'qualified_test_ride', 'attended_test_ride',
    'deposit', 'purchase',
  ]);
  assert.equal(measurement.kpis.length, 5);
  const depositTarget = measurement.kpis.find(item => item.id === 'count_deposit');
  assert.equal(depositTarget?.target, 525);
  assert.equal(depositTarget?.windowDays, 14);
});

test('report facts are reproducible and satisfy budget, formulas, matrix, and funnel invariants', () => {
  const { input, measurement, rows } = buildVoltRide();
  assert.deepEqual(rows, simulateReportFacts(input, measurement));
  const validation = validateReportFacts(input, measurement, rows);
  assert.equal(validation.rowCount, rows.length);
  assert.ok(validation.spend <= input.budget);
  assert.equal(new Set(rows.map(row => `${row.date}:${row.placementId}`)).size, rows.length);
});

test('evidence v2 evaluates KPI status and exposes evidence-bounded actions', () => {
  const { contract } = buildVoltRide();
  assert.equal(contract.contractVersion, 'report-evidence-v2');
  assert.equal(contract.kpiScorecard.length, 5);
  assert.ok(new Set(contract.kpiScorecard.map(item => item.status)).size >= 2);
  assert.ok(['good', 'watch', 'bad'].includes(contract.performanceStatus.status));
  assert.ok(contract.actions.length >= 2);
  for (const action of contract.actions) {
    assert.ok(action.evidenceIds.length);
    assert.ok(action.proposedAction);
    assert.ok(action.guardrail);
    assert.ok(action.nextReviewWindow);
  }
});

test('conversion questions name the campaign business outcomes instead of generic conversions', () => {
  const { contract } = buildVoltRide();
  const text = questionsForReport('conversion', contract).map(item => item.question).join(' ');
  assert.match(text, /Đăng ký lái thử/);
  assert.match(text, /Purchase|đặt cọc/i);
  assert.doesNotMatch(text, /Conversion funnel analysis/);
});

test('evidence fallback returns complete answers and actions instead of question placeholders', () => {
  const { input, contract } = buildVoltRide();
  const questions = questionsForReport('conversion', contract);
  const analysis = buildEvidenceAnalysis(input, contract, 'conversion', questions);
  assert.equal(analysis.questions.length, questions.length);
  assert.equal(analysis.analysisProvenance.provider, 'deterministic_fallback');
  for (const item of analysis.questions) {
    const sections = item.answer.sections;
    assert.ok(sections.some(section => section.type === 'summary' && section.text.length > 30));
    assert.ok(sections.some(section => section.type === 'insight'));
    assert.ok(sections.some(section => section.type === 'recommendation' && section.items.length));
  }
});

test('model prose cannot soften a deterministic BAD status or replace contract actions', () => {
  const { contract } = buildVoltRide();
  assert.equal(contract.performanceStatus.status, 'bad');
  const modelResult = {
    overall: 'Kết luận: Watch vì chi phí chỉ lệch nhẹ.',
    questions: [{
      id: 'cv_q1', findingIds: ['kpi_scorecard'],
      answer: { sections: [
        { type: 'summary', text: 'Model explanation remains available.' },
        { type: 'insight', level: 'watch', text: 'Campaign chỉ cần theo dõi.' },
        { type: 'recommendation', items: [{ priority: 'low', text: 'Tiếp tục như cũ.' }] },
      ] },
    }],
  };
  const grounded = groundAnalysisResult(modelResult, contract);
  assert.match(grounded.overall, /BAD/);
  assert.doesNotMatch(grounded.overall, /Watch/i);
  const insight = grounded.questions[0].answer.sections.find(item => item.type === 'insight');
  assert.equal(insight.level, 'bad');
  assert.match(insight.text, /2 KPI chưa đạt/);
  const recommendation = grounded.questions[0].answer.sections.find(item => item.type === 'recommendation');
  assert.equal(recommendation.items[0].actionId, contract.actions[0].id);
  assert.match(recommendation.items[0].text, /Guardrail:/);
});

test('near-schema model output with object sections is normalized before grounding', () => {
  const { contract } = buildVoltRide();
  const grounded = groundAnalysisResult({
    overall: 'Watch',
    questions: {
      cv_q1: {
        findingIds: ['kpi_scorecard'],
        answer: {
          sections: {
            summary: 'Phễu cần tối ưu.',
            metrics: [{ metricId: 'deposit', label: 'Đặt cọc', value: '408' }],
            insight: { level: 'watch', text: 'Theo dõi thêm.' },
            recommendation: ['Tiếp tục như cũ.'],
          },
        },
      },
    },
  }, contract);
  assert.ok(Array.isArray(grounded.questions));
  assert.ok(Array.isArray(grounded.questions[0].answer.sections));
  assert.equal(grounded.questions[0].answer.sections.find(item => item.type === 'insight').level, 'bad');
  assert.equal(
    grounded.questions[0].answer.sections.find(item => item.type === 'recommendation').items[0].actionId,
    contract.actions[0].id,
  );
  const metric = grounded.questions[0].answer.sections.find(item => item.type === 'metrics').items[0];
  assert.equal(metric.value, '408');
  assert.equal(metric.label, 'Đặt cọc');
});

test('business outcome actions choose cost-per-outcome evidence instead of CTR alone', () => {
  const input = normalizeReportInput({
    campaignId: 'OUTCOME-ZONE', brand: 'Outcome', objective: 'conversion',
    budget: 10_000_000, startDate: '2026-08-01', endDate: '2026-08-01',
    zones: [{ id: 'high_ctr' }, { id: 'efficient_outcome' }],
  });
  const measurement = {
    version: 'measurement-spec-v2', objective: 'conversion',
    optimizationEvent: 'lead', primaryOutcome: 'lead',
    outcomeGraph: { events: [{ id: 'lead', label: 'Lead', baseRate: 0.03 }], transitions: [] },
    kpis: [{
      id: 'count_lead', label: 'Lead', metric: 'event_count', eventId: 'lead',
      operator: '>=', target: 100, unit: 'count', source: 'brief',
    }],
    assumptions: {},
  };
  const rows = [
    { campaignId: input.campaignId, placementId: 'high_ctr', date: input.startDate,
      impressions: 1000, clicks: 100, spend: 1_000_000, conversions: 10, reach: 700, vi: 80,
      outcomes: { lead: 10 } },
    { campaignId: input.campaignId, placementId: 'efficient_outcome', date: input.startDate,
      impressions: 1000, clicks: 20, spend: 500_000, conversions: 20, reach: 700, vi: 80,
      outcomes: { lead: 20 } },
  ];
  const contract = buildReportContract(input, rows, measurement);
  assert.match(contract.actions[0].proposedAction, /efficient_outcome/);
  assert.ok(contract.actions[0].evidenceIds.includes('outcome_zone_efficiency'));
  assert.ok(contract.findings.some(item => item.id === 'outcome_zone_efficiency'));

  const grounded = groundAnalysisResult({
    overall: 'Bad',
    questions: [{
      id: 'cv_q3', findingIds: ['outcome_zone_efficiency'],
      answer: { sections: [{
        type: 'metrics', items: [
          { metricId: 'lead', label: 'Lead tại zone', value: '999999' },
        ],
      }] },
    }],
  }, contract);
  const metric = grounded.questions[0].answer.sections[0].items[0];
  assert.equal(metric.label, 'Lead · efficient_outcome');
  assert.equal(metric.value, '20');
});

test('deposit is not injected into an unrelated purchase campaign', () => {
  const input = normalizeReportInput({
    ...fixture,
    campaignId: 'ECOMMERCE-V2',
    brand: 'ShopNow',
    kpi: 'Tối thiểu 1.000 đơn hàng. CPA đơn hàng không quá 120.000 VND.',
    notes: 'Theo dõi product view, checkout và purchase.',
  });
  const ids = buildMeasurementSpec(input).outcomeGraph.events.map(item => item.id);
  assert.ok(ids.includes('purchase'));
  assert.ok(!ids.includes('deposit'));
});

test('Awareness evaluates Viewability and CPM from the brief', () => {
  const input = normalizeReportInput({
    ...fixture, campaignId: 'AWARENESS-V2', objective: 'awareness',
    kpi: 'Viewability tối thiểu 75%. CPM không vượt quá 55.000 VND.',
    notes: 'Tăng nhận diện bằng video hoàn tất.',
  });
  const measurement = buildMeasurementSpec(input);
  assert.deepEqual(measurement.kpis.map(item => item.metricId), ['viewability', 'cpm']);
  const contract = buildReportContract(input, simulateReportFacts(input, measurement), measurement);
  assert.equal(contract.kpiScorecard.length, 2);
  assert.ok(contract.kpiScorecard.every(item => Number.isFinite(item.actual)));
});

test('Consideration evaluates CTR while Retention evaluates its outcome transition', () => {
  const consideration = normalizeReportInput({
    ...fixture, campaignId: 'CONSIDERATION-V2', objective: 'consideration',
    kpi: 'CTR tối thiểu 0,8%. Tối thiểu 5.000 clicks.', notes: 'Tăng product view.',
  });
  const considerationSpec = buildMeasurementSpec(consideration);
  assert.deepEqual(considerationSpec.kpis.map(item => item.metricId), ['ctr', 'clicks']);

  const retention = normalizeReportInput({
    ...fixture, campaignId: 'RETENTION-V2', objective: 'retention',
    kpi: 'Tỷ lệ retained 30 ngày tối thiểu 50%.', notes: 'Re-engagement người dùng cũ.',
  });
  const retentionSpec = buildMeasurementSpec(retention);
  assert.equal(retentionSpec.kpis[0].numeratorEvent, 'retained_30d');
  assert.equal(retentionSpec.kpis[0].denominatorEvent, 're_engagement');
  assert.equal(retentionSpec.kpis[0].target, 50);
});

test('legacy report callers retain a 14-day default and evidence v1 compatibility', () => {
  const input = normalizeReportInput({
    campaignId: 'LEGACY', brand: 'Legacy', objective: 'awareness', budget: 10_000_000,
    startDate: '2026-08-01', zones: [{ id: 'z1', cpm: 40_000 }],
  });
  assert.equal(input.durationDays, 14);
  const legacy = buildReportContract(input, [{
    campaignId: 'LEGACY', placementId: 'z1', date: '2026-08-01',
    impressions: 1000, clicks: 10, spend: 40_000, conversions: 1, reach: 700, vi: 80,
  }]);
  assert.equal(legacy.contractVersion, 'report-evidence-v1');
});

test('legacy missing budget keeps the prior backend default and impossible dates fail closed', () => {
  const legacy = normalizeReportInput({
    campaignId: 'LEGACY-DEFAULT', startDate: '2026-08-01', zones: ['z1'],
  });
  assert.equal(legacy.budget, 100_000_000);
  assert.throws(() => normalizeReportInput({
    campaignId: 'BAD-DATE', startDate: '2026-02-30', zones: ['z1'],
  }), /invalid report date/);
});

test('caller-supplied measurement specs fail closed when outcome references are malformed', () => {
  const input = normalizeReportInput({
    ...fixture,
    campaignId: 'INVALID-MEASUREMENT',
    measurementSpec: {
      version: 'measurement-spec-v2',
      optimizationEvent: 'missing',
      primaryOutcome: 'purchase',
      outcomeGraph: { events: [{ id: 'purchase' }], transitions: [] },
      kpis: [],
    },
  });
  assert.throws(() => buildMeasurementSpec(input), /invalid measurement spec/);
});
