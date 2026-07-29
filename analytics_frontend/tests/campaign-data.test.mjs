import test from 'node:test';
import assert from 'node:assert/strict';
import {
  campaignOptions,
  filterRecords,
  requestedCampaignId
} from '../campaign-data.js';

test('campaign options preserve exact order IDs and add human-readable brand labels', () => {
  const options = campaignOptions(
    [
      { campaignId: 'ORD-2026-012' },
      { campaignId: 'ORD-2026-013' },
      { campaignId: 'lab-demo-1' }
    ],
    [
      { id: 'ORD-2026-012', brand: 'Miniapp Đi Cùng Con' },
      { id: 'ORD-2026-013', brand: 'Hutao shop' }
    ]
  );

  assert.deepEqual(
    options.map(option => option.value),
    ['ORD-2026-013', 'ORD-2026-012', 'lab-demo-1']
  );
  assert.equal(options[0].label, 'Hutao shop · ORD-2026-013');
  assert.notEqual(options[0].value, 'ORD-2026');
});

test('campaign deep link reads the exact campaign ID', () => {
  assert.equal(
    requestedCampaignId('?campaignId=ORD-2026-013'),
    'ORD-2026-013'
  );
  assert.equal(requestedCampaignId('?other=value'), '');
});

test('record filtering never merges campaigns with the same prefix', () => {
  const records = [
    { campaignId: 'ORD-2026-012', placementId: 'A', channel: 'Znews', date: '2026-07-01' },
    { campaignId: 'ORD-2026-013', placementId: 'B', channel: 'BaoMoi', date: '2026-07-02' }
  ];

  assert.deepEqual(
    filterRecords(records, { brand: 'ORD-2026-013' }),
    [records[1]]
  );
  assert.deepEqual(
    filterRecords(records, { brand: 'ORD-2026' }),
    []
  );
});
