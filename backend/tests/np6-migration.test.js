const assert = require('node:assert/strict');
const test = require('node:test');

const {
  deploymentIdFromArgs,
  stableCatalogHash,
  validateLegacyContracts,
} = require('../seed/migrate-np6-catalog');

function placement(overrides = {}) {
  return {
    id: 'Legacy_One',
    channel: 'legacy-channel',
    format: 'banner',
    size: '300x250',
    reach: 1000,
    vi: 60,
    ctr: 0.4,
    cpm: 25000,
    obj: 'awareness',
    metricSource: 'synthetic_inventory_v2',
    inventoryTier: 'standard-box',
    testSiteZone: 'Legacy_One',
    siteId: 'legacy',
    siteUrl: 'https://legacy.example/',
    ...overrides,
  };
}

test('NP-6 migration accepts unchanged legacy contracts with additive metadata', () => {
  const expected = placement();
  const current = placement({ audienceContext: { topics: ['business_finance'] } });
  assert.doesNotThrow(() =>
    validateLegacyContracts({ placements: [current] }, { placements: [expected] })
  );
});

test('NP-6 migration rejects a changed legacy inventory contract', () => {
  assert.throws(
    () =>
      validateLegacyContracts(
        { placements: [placement({ cpm: 99999 })] },
        { placements: [placement()] }
      ),
    /legacy contract differs/
  );
});

test('NP-6 migration hash changes when catalog content changes', () => {
  const first = {
    catalogVersion: 'legacy-35',
    placements: [placement()],
  };
  const second = {
    ...first,
    placements: [placement({ reach: 2000 })],
  };
  assert.notEqual(stableCatalogHash(first), stableCatalogHash(second));
});

test('NP-6 migration reads an explicit deployment id', () => {
  assert.equal(
    deploymentIdFromArgs(['node', 'script', '--apply', '--deployment-id=np6-test']),
    'np6-test'
  );
});
