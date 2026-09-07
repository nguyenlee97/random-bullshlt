'use strict';

const { buildRuntimeFixture } = require('./investigationFixtures');

const INTERVENTIONS = Object.freeze([
  'restore_delivery',
  'restore_click_measurement',
  'replace_creative_fixture',
  'remove_click_overlay_fixture',
  'restore_config_fixture',
  'switch_placement_fixture',
  'backfill_attribution_fixture',
]);
const INTERVENTION_SET = new Set(INTERVENTIONS);
const ACTION_INTERVENTIONS = Object.freeze({
  hold_optimization_and_recheck: [
    'restore_delivery', 'restore_click_measurement', 'replace_creative_fixture',
    'restore_config_fixture', 'backfill_attribution_fixture',
  ],
  request_measurement_reconciliation: ['restore_click_measurement'],
  prepare_creative_replacement: ['replace_creative_fixture'],
  propose_placement_switch: ['switch_placement_fixture'],
  prepare_click_surface_fix: ['remove_click_overlay_fixture'],
  prepare_report_pipeline_fix: ['backfill_attribution_fixture'],
});

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round((Number(value) || 0) * factor) / factor;
}

function derived(row) {
  const impressions = Math.max(0, Math.round(Number(row.impressions) || 0));
  const clicks = Math.min(impressions, Math.max(0, Math.round(Number(row.clicks) || 0)));
  const spend = Math.max(0, Math.round(Number(row.spend) || 0));
  return {
    ...row, impressions, clicks, spend,
    conversions: Math.max(0, Math.round(Number(row.conversions) || 0)),
    reach: Math.min(impressions, Math.max(0, Math.round(Number(row.reach) || 0))),
    outcomes: Object.fromEntries(Object.entries(row.outcomes || {}).map(([key, value]) => (
      [key, Math.max(0, Math.round(Number(value) || 0))]
    ))),
    ctr: impressions ? round(clicks / impressions * 100) : 0,
    cpm: impressions ? round(spend / impressions * 1000) : 0,
  };
}

function validate(config = {}) {
  const interventionType = String(config.interventionType || '').trim();
  if (!INTERVENTION_SET.has(interventionType)) throw new Error('unknown recovery intervention');
  const proposalId = String(config.proposalId || '').trim();
  const actionId = String(config.actionId || '').trim();
  if (!/^RP-[A-Z0-9]{6,20}$/.test(proposalId)) throw new Error('valid proposalId is required');
  if (!/^[a-z0-9_]{3,80}$/.test(actionId)) throw new Error('valid actionId is required');
  if (!(ACTION_INTERVENTIONS[actionId] || []).includes(interventionType)) {
    throw new Error('recovery action does not allow this intervention');
  }
  const outcome = config.outcome === 'ineffective' ? 'ineffective' : 'success';
  return { interventionType, proposalId, actionId, outcome };
}

function key(row) { return `${row.placementId || ''}|${row.date || ''}`; }

function recentDates(records, count) {
  return new Set([...new Set(records.map(row => row.date).filter(Boolean))].sort().slice(-count));
}

function blend(before, target, ratio) {
  return (Number(before) || 0) + ((Number(target) || 0) - (Number(before) || 0)) * ratio;
}

function blendOutcomes(before, target, ratio) {
  const names = new Set([...Object.keys(before || {}), ...Object.keys(target || {})]);
  return Object.fromEntries([...names].map(name => [name, blend(before?.[name], target?.[name], ratio)]));
}

function applyRecoveryIntervention(baselineValue, activeValue, scenarioValue, configValue) {
  const config = validate(configValue);
  const baseline = (baselineValue || []).map(row => structuredClone(row));
  const active = (activeValue || []).map(row => structuredClone(row));
  if (!baseline.length || !active.length) throw new Error('recovery requires baseline and active records');
  const baselineByKey = new Map(baseline.map(row => [key(row), row]));
  const scenario = scenarioValue || active.find(row => row.scenario)?.scenario || {};
  const targetPlacementId = String(
    configValue.targetPlacementId || scenario.targetPlacementId || active[0]?.placementId || '',
  );
  if (!active.some(row => String(row.placementId) === targetPlacementId)) {
    throw new Error('target placement is not in this campaign dataset');
  }
  const windowCount = Math.max(1, Number(scenario.windowDays || 3) * Number(scenario.persistenceWindows || 2));
  const dates = recentDates(active, windowCount);
  const ratio = config.outcome === 'success' ? 1 : 0.35;
  const metricSets = {
    restore_delivery: ['impressions', 'clicks', 'reach', 'spend', 'conversions', 'outcomes'],
    restore_click_measurement: ['clicks', 'conversions', 'outcomes'],
    replace_creative_fixture: ['impressions', 'clicks', 'reach', 'spend', 'conversions', 'outcomes'],
    remove_click_overlay_fixture: ['clicks', 'conversions', 'outcomes'],
    restore_config_fixture: [],
    switch_placement_fixture: ['impressions', 'clicks', 'reach', 'spend', 'conversions', 'outcomes'],
    backfill_attribution_fixture: ['conversions', 'outcomes'],
  };
  const fields = metricSets[config.interventionType];
  const records = active.map(original => {
    const target = baselineByKey.get(key(original));
    const inScope = String(original.placementId) === targetPlacementId && dates.has(original.date);
    let row = { ...original, outcomes: { ...(original.outcomes || {}) } };
    if (target && inScope) {
      for (const field of fields) {
        row[field] = field === 'outcomes'
          ? blendOutcomes(row[field], target[field], ratio)
          : blend(row[field], target[field], ratio);
      }
    }
    const signals = { ...((row.scenario || {}).signals || {}) };
    if (config.outcome === 'success' && inScope) {
      if (config.interventionType === 'replace_creative_fixture') signals.creativeRenderFailure = false;
      if (config.interventionType === 'restore_click_measurement') signals.clickTelemetryFailure = false;
      if (config.interventionType === 'backfill_attribution_fixture') signals.trackingDelay = false;
    }
    if (config.outcome === 'success' && config.interventionType === 'restore_config_fixture') {
      signals.configDrift = false;
    }
    return derived({
      ...row,
      scenario: {
        ...scenario,
        signals,
        recovery: { ...config, parentRevision: configValue.parentRevision },
      },
    });
  });
  let runtimeFixture = null;
  if (scenario.presetId === 'click_overlay') {
    const fixtureConfig = config.interventionType === 'remove_click_overlay_fixture' && config.outcome === 'success'
      ? { ...scenario, presetId: 'healthy_baseline' } : scenario;
    runtimeFixture = buildRuntimeFixture(fixtureConfig, [...new Set(active.map(row => row.placementId))]);
  }
  return {
    config: { ...config, targetPlacementId, parentRevision: configValue.parentRevision },
    records, runtimeFixture,
  };
}

module.exports = { INTERVENTIONS, ACTION_INTERVENTIONS, applyRecoveryIntervention };
