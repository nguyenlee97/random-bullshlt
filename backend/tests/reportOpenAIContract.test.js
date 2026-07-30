const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildOpenAIRequestBody,
  normalizeGeneratedRecordsToBudget,
} = require('../services/reportGenerator');


test('GPT-5 report calls use max_completion_tokens without unsupported temperature', () => {
  const body = buildOpenAIRequestBody(
    'gpt-5.4-mini', [{ role: 'user', content: 'report' }], 0.6, 8000
  );
  assert.equal(body.max_completion_tokens, 8000);
  assert.equal('max_tokens' in body, false);
  assert.equal('temperature' in body, false);
  assert.deepEqual(body.response_format, { type: 'json_object' });
});


test('older report models retain their configured sampling temperature', () => {
  const body = buildOpenAIRequestBody(
    'gpt-4.1-mini', [{ role: 'user', content: 'report' }], 0.6, 8000
  );
  assert.equal(body.temperature, 0.6);
});


test('new over-budget report delivery is scaled without changing ratios', () => {
  const records = [
    {
      placementId: 'zone-a', impressions: 1_000_000, clicks: 10_000,
      spend: 100_000_000, reach: 700_000, conversions: 200,
      ctr: 1, cpm: 100_000, vi: 80,
    },
    {
      placementId: 'zone-b', impressions: 2_000_000, clicks: 40_000,
      spend: 100_000_000, reach: 1_200_000, conversions: 400,
      ctr: 2, cpm: 50_000, vi: 70,
    },
  ];

  const normalized = normalizeGeneratedRecordsToBudget(records, 100_000_000);
  const total = key => normalized.reduce((sum, row) => sum + row[key], 0);

  assert.equal(total('spend'), 85_000_000);
  assert.equal(total('impressions'), 1_275_000);
  assert.equal(total('clicks'), 21_250);
  assert.equal(total('reach'), 807_500);
  assert.equal(total('conversions'), 255);
  assert.equal(total('spend') / total('impressions'), 200_000_000 / 3_000_000);
  assert.equal(total('clicks') / total('impressions'), 50_000 / 3_000_000);
  assert.equal(normalized[0].vi, 80);
});


test('new report delivery already within budget is not modified', () => {
  const records = [{
    impressions: 1_000, clicks: 10, spend: 80_000_000,
    reach: 700, conversions: 2, ctr: 1, cpm: 80_000_000,
  }];

  assert.equal(normalizeGeneratedRecordsToBudget(records, 100_000_000), records);
});
