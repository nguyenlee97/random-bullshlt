const test = require('node:test');
const assert = require('node:assert/strict');

const { deriveInventoryMetrics } = require('../seed/index');

test('synthetic inventory metrics follow placement prominence', () => {
  const channelReach = 1_000_000;
  const masthead = deriveInventoryMetrics(
    { id: 'ZingNews_Masthead', channel: 'znews-site' }, channelReach,
  );
  const middle = deriveInventoryMetrics(
    { id: 'ZingNews_Halfpage', channel: 'znews-site' }, channelReach,
  );
  const box = deriveInventoryMetrics(
    { id: 'Znews_Home_SidebarBox', channel: 'znews-site' }, channelReach,
  );

  assert.ok(masthead.cpm > middle.cpm);
  assert.ok(middle.cpm > box.cpm);
  assert.ok(masthead.reach > middle.reach);
  assert.ok(middle.reach > box.reach);
  assert.equal(masthead.metricSource, 'synthetic_inventory_v2');
});

test('category and side position produce distinct, bounded metrics', () => {
  const sportsLeft = deriveInventoryMetrics(
    { id: 'Znews_TheThao_SideLeft', channel: 'znews-the-thao' }, 500_000,
  );
  const sportsRight = deriveInventoryMetrics(
    { id: 'Znews_TheThao_SideRight', channel: 'znews-the-thao' }, 500_000,
  );
  const lifestyleLeft = deriveInventoryMetrics(
    { id: 'Znews_DoiSong_SideLeft', channel: 'znews-doi-song' }, 380_000,
  );

  assert.ok(sportsLeft.cpm > sportsRight.cpm);
  assert.ok(sportsLeft.reach > sportsRight.reach);
  assert.ok(sportsLeft.cpm > lifestyleLeft.cpm);
  assert.ok(sportsLeft.reach <= 500_000);
  assert.ok(lifestyleLeft.reach <= 380_000);
});
