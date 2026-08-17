const test = require('node:test');
const assert = require('node:assert/strict');

const {
  aggregate, buildReportContract, validateAnalysisResult,
} = require('../lib/reportContract');

const records = [
  { placementId: 'a', date: '2026-07-20', impressions: 1000, clicks: 10, spend: 20000, conversions: 2, reach: 700, vi: 80 },
  { placementId: 'a', date: '2026-07-21', impressions: 2000, clicks: 30, spend: 50000, conversions: 3, reach: 1300, vi: 70 },
  { placementId: 'b', date: '2026-07-21', impressions: 500, clicks: 4, spend: 15000, conversions: 0, reach: 350, vi: 90 },
];

test('report contract derives traceable formulas and labels synthetic data', () => {
  const metrics = aggregate(records);
  assert.equal(metrics.impressions, 3500);
  assert.equal(metrics.clicks, 44);
  assert.equal(metrics.ctr, 1.257);
  assert.equal(metrics.summed_daily_reach, 2350);

  const contract = buildReportContract({ campaignId: 'c1', objective: 'awareness' }, records);
  assert.equal(contract.synthetic, true);
  assert.equal(contract.source, 'synthetic_showcase');
  assert.equal(contract.timeframe.start, '2026-07-20');
  assert.equal(contract.timeframe.end, '2026-07-21');
  assert.match(contract.metricDefinitions.summed_daily_reach.limitation, /Not deduplicated/);
});

test('invented metric or finding makes report analysis fail validation', () => {
  const contract = buildReportContract({ campaignId: 'c1', objective: 'awareness' }, records);
  const expected = [{ id: 'q1' }];
  assert.throws(() => validateAnalysisResult({
    overall: 'Synthetic report.',
    questions: [{
      id: 'q1', findingIds: ['invented_finding'],
      answer: { sections: [{ type: 'metrics', items: [{ metricId: 'magic_roi' }] }] },
    }],
  }, expected, contract), /unknown findings|invented metric/);
});

test('validated answers cite known findings and metric IDs', () => {
  const contract = buildReportContract({ campaignId: 'c1', objective: 'awareness' }, records);
  const result = validateAnalysisResult({
    overall: 'Dữ liệu mô phỏng.',
    questions: [{
      id: 'q1', findingIds: ['campaign_totals'],
      answer: { sections: [{ type: 'metrics', items: [{ metricId: 'ctr', value: '1.257%' }] }] },
    }],
  }, [{ id: 'q1' }], contract);
  assert.equal(result.questions[0].findingIds[0], 'campaign_totals');
});
