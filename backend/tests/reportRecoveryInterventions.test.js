'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { applyScenario } = require('../lib/reportScenarios');
const { INTERVENTIONS, applyRecoveryIntervention } = require('../lib/reportRecoveryInterventions');

const baseline = ['2026-08-01', '2026-08-02'].flatMap(date => [
  { campaignId: 'ORD-1', placementId: 'zone-a', date, impressions: 1000, clicks: 20,
    spend: 50000, reach: 800, conversions: 5, outcomes: { lead: 5 } },
  { campaignId: 'ORD-1', placementId: 'zone-b', date, impressions: 800, clicks: 24,
    spend: 40000, reach: 600, conversions: 6, outcomes: { lead: 6 } },
]);

function recover(presetId, interventionType, outcome = 'success') {
  const scenario = applyScenario(baseline, {
    presetId, targetPlacementId: 'zone-a', windowDays: 1, persistenceWindows: 1, impact: 0.8,
  });
  return {
    scenario,
    recovered: applyRecoveryIntervention(baseline, scenario.records, scenario.config, {
      proposalId: 'RP-ABCDEF12',
      actionId: {
        restore_click_measurement: 'request_measurement_reconciliation',
        remove_click_overlay_fixture: 'prepare_click_surface_fix',
      }[interventionType] || 'hold_optimization_and_recheck',
      interventionType,
      outcome, parentRevision: 2,
    }),
  };
}

test('intervention registry is closed and rejects arbitrary commands', () => {
  assert.equal(INTERVENTIONS.length, 7);
  assert.throws(() => applyRecoveryIntervention(baseline, baseline, {}, {
    proposalId: 'RP-ABCDEF12', actionId: 'hold_optimization_and_recheck', interventionType: 'run_shell',
  }), /unknown recovery intervention/);
  assert.throws(() => applyRecoveryIntervention(baseline, baseline, {}, {
    proposalId: 'RP-ABCDEF12', actionId: 'prepare_creative_replacement',
    interventionType: 'restore_click_measurement',
  }), /does not allow/);
});

test('click recovery restores only the selected recent synthetic scope', () => {
  const { recovered } = recover('click_tracking_failure', 'restore_click_measurement');
  const target = recovered.records.find(row => row.placementId === 'zone-a' && row.date === '2026-08-02');
  const oldTarget = recovered.records.find(row => row.placementId === 'zone-a' && row.date === '2026-08-01');
  const other = recovered.records.find(row => row.placementId === 'zone-b' && row.date === '2026-08-02');
  assert.equal(target.clicks, 20);
  assert.equal(target.scenario.signals.clickTelemetryFailure, false);
  assert.equal(target.scenario.recovery.parentRevision, 2);
  assert.equal(oldTarget.clicks, 20);
  assert.equal(other.clicks, 24);
});

test('overlay recovery removes isolated obstruction without leaking preset into page', () => {
  const { recovered } = recover('click_overlay', 'remove_click_overlay_fixture');
  assert.match(recovered.runtimeFixture.pages['zone-a'], /pointer-events:none/);
  assert.doesNotMatch(JSON.stringify(recovered.runtimeFixture), /click_overlay|groundTruth/);
});

test('ineffective recovery remains measurably below baseline', () => {
  const { recovered } = recover('low_ctr', 'restore_click_measurement', 'ineffective');
  const target = recovered.records.find(row => row.placementId === 'zone-a' && row.date === '2026-08-02');
  assert.ok(target.clicks > 4);
  assert.ok(target.clicks < 20);
  assert.equal(target.scenario.recovery.outcome, 'ineffective');
});
