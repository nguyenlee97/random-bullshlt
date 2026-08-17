const assert = require('node:assert/strict');
const test = require('node:test');

const {
  audienceSizeEstimate,
  withAudienceSizeEstimate,
} = require('../lib/audienceSizeEstimate');

test('preserves publisher catalog sizes', () => {
  const source = { segmentId: 'INT059', sizeMin: 25_213_990, sizeMax: 30_549_968 };
  const result = withAudienceSizeEstimate(source);
  assert.equal(result.sizeMin, source.sizeMin);
  assert.equal(result.sizeMax, source.sizeMax);
  assert.equal(result.sizeSource, 'catalog');
});

test('creates stable realistic ranges for missing Vietnam audience sizes', () => {
  const source = {
    segmentId: 'INT042',
    type: 'Interest',
    category: 'Entertainment (leisure)',
    fullLabel: 'Action games (video games)',
  };
  const first = audienceSizeEstimate(source);
  const second = audienceSizeEstimate(source);
  assert.deepEqual(first, second);
  assert.equal(first.sizeSource, 'modeled_estimate');
  assert.ok(first.sizeMin >= 100_000);
  assert.ok(first.sizeMax <= 10_000_000);
  assert.ok(first.sizeMax > first.sizeMin);
  assert.match(first.sizeRaw, /^\d[\d.]*(?: - )\d[\d.]*$/);
});

test('uses a narrower plausible range for expat behavior', () => {
  const result = audienceSizeEstimate({
    segmentId: 'BEH006', type: 'Behavior', category: 'Expats', name: 'Expats',
  });
  assert.ok(result.sizeMin >= 50_000);
  assert.ok(result.sizeMax <= 1_000_000);
});
