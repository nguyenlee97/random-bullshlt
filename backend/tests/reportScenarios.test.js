'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { PRESETS, scenarioConfig, applyScenario, expectationFor } = require('../lib/reportScenarios');

const rows = [
  { campaignId: 'ORD-1', placementId: 'zone-a', date: '2026-08-01', impressions: 1000, clicks: 20, spend: 50000, reach: 800, conversions: 5, outcomes: { lead: 5 }, vi: 80 },
  { campaignId: 'ORD-1', placementId: 'zone-a', date: '2026-08-02', impressions: 1000, clicks: 20, spend: 50000, reach: 800, conversions: 5, outcomes: { lead: 5 }, vi: 80 },
  { campaignId: 'ORD-1', placementId: 'zone-b', date: '2026-08-02', impressions: 800, clicks: 24, spend: 40000, reach: 600, conversions: 6, outcomes: { lead: 6 }, vi: 78 },
];

test('scenario catalog exposes the complete evaluation set', () => {
  assert.equal(PRESETS.length, 12);
  assert.ok(PRESETS.some(item => item.id === 'multiple_issues'));
  assert.ok(PRESETS.some(item => item.id === 'recovery_ineffective'));
  assert.ok(PRESETS.every(item => item.expectation && Array.isArray(item.expectation.l1IssueTypes)));
  assert.equal(PRESETS.find(item => item.id === 'poor_placement').issueType, 'ctr_regression');
  assert.deepEqual(expectationFor('multiple_issues').l1IssueTypes, ['delivery_drop', 'ctr_regression']);
  const copy = expectationFor('low_ctr'); copy.l1IssueTypes.push('forged');
  assert.deepEqual(expectationFor('low_ctr').l1IssueTypes, ['ctr_regression']);
});

test('low impression scenario changes only the selected recent scope and recomputes ratios', () => {
  const result = applyScenario(rows, {
    presetId: 'low_impression_zone', targetPlacementId: 'zone-a',
    windowDays: 1, persistenceWindows: 1, impact: 0.8,
  });
  const oldTarget = result.records.find(row => row.placementId === 'zone-a' && row.date === '2026-08-01');
  const newTarget = result.records.find(row => row.placementId === 'zone-a' && row.date === '2026-08-02');
  const other = result.records.find(row => row.placementId === 'zone-b');
  assert.equal(oldTarget.impressions, 1000);
  assert.equal(newTarget.impressions, 200);
  assert.equal(newTarget.clicks, 4);
  assert.equal(newTarget.ctr, 2);
  assert.equal(other.impressions, 800);
});

test('click failure changes facts and leaves an explicit machine-readable signal', () => {
  const result = applyScenario(rows, {
    presetId: 'click_tracking_failure', targetPlacementId: 'zone-a', windowDays: 1,
  });
  const target = result.records.find(row => row.placementId === 'zone-a' && row.date === '2026-08-02');
  assert.equal(target.clicks, 0);
  assert.equal(target.conversions, 0);
  assert.equal(target.outcomes.lead, 0);
  assert.equal(target.scenario.signals.clickTelemetryFailure, true);
});

test('scenario validation rejects unknown presets and bounds custom controls', () => {
  assert.throws(() => scenarioConfig({ presetId: 'made_up' }), /unknown scenario preset/);
  const config = scenarioConfig({ presetId: 'low_ctr', impact: 2, windowDays: 999 });
  assert.equal(config.impact, 1);
  assert.equal(config.windowDays, 30);
});

test('click overlay changes metrics without revealing a technical answer flag', () => {
  const input = structuredClone(rows);
  const result = applyScenario(input, { presetId: 'click_overlay', targetPlacementId: 'zone-a' });
  assert.deepEqual(input, rows);
  assert.ok(result.records.filter(r => r.placementId === 'zone-a').every(r => r.clicks === 0));
  assert.ok(result.records.every(r => !Object.values(r.scenario.signals).some(Boolean)));
  assert.equal(result.runtimeFixture.version, 'isolated-page-v1');
  assert.match(result.runtimeFixture.pages['zone-a'], /pointer-events:auto/);
  assert.match(result.runtimeFixture.pages['zone-b'], /pointer-events:none/);
  assert.doesNotMatch(JSON.stringify(result.runtimeFixture), /click_overlay|presetId|groundTruth/);
  const healthy = applyScenario(input, { presetId: 'healthy_baseline' });
  assert.ok(Object.values(healthy.runtimeFixture.pages).every(page => page.includes('pointer-events:none')));
});
