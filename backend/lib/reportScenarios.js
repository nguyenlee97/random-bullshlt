'use strict';

const expectation = (l1IssueTypes, l2Hypotheses, requiredEvidence, note) => ({
  // These are minimum acceptance expectations under the default Evaluation
  // policy. Custom impact/window controls may intentionally produce less.
  l1IssueTypes, l2Hypotheses, requiredEvidence, note,
});

const PRESETS = Object.freeze([
  { id: 'healthy_baseline', label: 'Healthy baseline', issueType: null,
    expectation: expectation([], [], ['metrics_window'], 'Không mở incident mới; incident cũ có thể được resolve.') },
  { id: 'low_impression_zone', label: 'Low impression zone', issueType: 'delivery_drop',
    expectation: expectation(['delivery_drop', 'pacing_error'], ['inventory_shortfall'], ['delivery_pattern', 'spend_pacing'], 'Delivery và spend cùng giảm tại placement được chọn.') },
  { id: 'low_ctr', label: 'Normal impressions, low CTR', issueType: 'ctr_regression',
    expectation: expectation(['ctr_regression'], ['creative_underperformance'], ['metrics_window', 'click_telemetry', 'creative_compatibility'], 'Impression/spend giữ ổn định; response giảm.') },
  { id: 'creative_failure', label: 'Creative render or format failure', issueType: 'creative_failure',
    expectation: expectation(['creative_failure', 'delivery_drop', 'ctr_regression', 'pacing_error'], ['creative_render_failure'], ['creative_compatibility', 'delivery_pattern'], 'Tín hiệu kỹ thuật và delivery đều xấu.') },
  { id: 'click_tracking_failure', label: 'Click area or event failure', issueType: 'click_tracking_failure',
    expectation: expectation(['click_tracking_failure', 'ctr_regression'], ['click_tracking_failure'], ['click_telemetry', 'metrics_window'], 'Impression còn nhưng click telemetry bằng 0.') },
  { id: 'click_overlay', label: 'Click area covered — investigate rendered page', issueType: 'ctr_regression',
    expectation: expectation(['ctr_regression'], ['click_obstruction'], ['inspect_render', 'creative_compatibility'], 'Cần browser evidence; không có answer flag trong metrics.') },
  { id: 'config_drift', label: 'Campaign configuration drift', issueType: 'config_drift',
    expectation: expectation(['config_drift'], ['config_drift'], ['config_drift'], 'Preset cung cấp synthetic drift signal; order thật không bị sửa.') },
  { id: 'poor_placement', label: 'Poor placement with a better alternative', issueType: 'ctr_regression',
    expectation: expectation(['ctr_regression'], ['placement_underperformance'], ['placement_benchmark', 'creative_compatibility'], 'Alternative phải tồn tại trong catalog; booking availability vẫn chưa được giả định.') },
  { id: 'tracking_delay', label: 'Tracking delay or insufficient data', issueType: 'data_quality',
    expectation: expectation(['data_quality'], ['data_quality_incomplete'], ['data_completeness'], 'Không tối ưu performance trước khi attribution đủ dữ liệu.') },
  { id: 'multiple_issues', label: 'Multiple concurrent issues', issueType: 'multiple',
    expectation: expectation(['delivery_drop', 'ctr_regression'], ['inventory_shortfall', 'creative_underperformance'], ['delivery_pattern', 'metrics_window', 'spend_pacing'], 'Phải giữ nhiều incident/hypothesis độc lập, không ép thành một root cause.') },
  { id: 'recovery_success', label: 'Successful recovery', issueType: 'recovery_verification',
    expectation: expectation([], [], ['metrics_window'], 'Trở về baseline; verification có thể resolve incident cũ.') },
  { id: 'recovery_ineffective', label: 'Ineffective recovery', issueType: 'recovery_verification',
    expectation: expectation(['delivery_drop', 'ctr_regression'], ['inventory_shortfall', 'creative_underperformance'], ['delivery_pattern', 'metrics_window'], 'Recovery signal không đủ chứng minh thành công; vấn đề vẫn phải tái hiện.') },
]);

const PRESET_IDS = new Set(PRESETS.map(item => item.id));

function expectationFor(presetId) {
  const preset = PRESETS.find(item => item.id === presetId);
  return preset ? JSON.parse(JSON.stringify(preset.expectation)) : null;
}

function numberBetween(value, fallback, min, max) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
}

function scenarioConfig(value = {}) {
  const presetId = String(value.presetId || value.preset_id || '').trim();
  if (!PRESET_IDS.has(presetId)) throw new Error('unknown scenario preset');
  return {
    presetId,
    targetPlacementId: String(value.targetPlacementId || value.target_placement_id || '').trim() || null,
    windowDays: Math.round(numberBetween(value.windowDays ?? value.window_days, 3, 1, 30)),
    persistenceWindows: Math.round(numberBetween(
      value.persistenceWindows ?? value.persistence_windows, 2, 1, 10,
    )),
    impact: numberBetween(value.impact, 0.75, 0, 1),
    seed: String(value.seed || 'default'),
  };
}

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round((Number(value) || 0) * factor) / factor;
}

function derived(row) {
  const impressions = Math.max(0, Math.round(Number(row.impressions) || 0));
  const clicks = Math.min(impressions, Math.max(0, Math.round(Number(row.clicks) || 0)));
  const spend = Math.max(0, Math.round(Number(row.spend) || 0));
  const outcomes = Object.fromEntries(Object.entries(row.outcomes || {}).map(([key, value]) => (
    [key, Math.max(0, Math.round(Number(value) || 0))]
  )));
  return {
    ...row,
    impressions,
    clicks,
    spend,
    conversions: Math.max(0, Math.round(Number(row.conversions) || 0)),
    reach: Math.min(impressions, Math.max(0, Math.round(Number(row.reach) || 0))),
    vi: round(Math.min(100, Math.max(0, Number(row.vi) || 0)), 2),
    outcomes,
    ctr: impressions ? round(clicks / impressions * 100) : 0,
    cpm: impressions ? round(spend / impressions * 1000) : 0,
  };
}

function recentDates(records, windowDays) {
  return new Set([...new Set(records.map(row => row.date).filter(Boolean))].sort().slice(-windowDays));
}

function resolveTarget(records, requested) {
  if (requested && records.some(row => row.placementId === requested)) return requested;
  const totals = new Map();
  for (const row of records) {
    totals.set(row.placementId, (totals.get(row.placementId) || 0) + (Number(row.impressions) || 0));
  }
  return [...totals.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || null;
}

function scaleOutcomes(outcomes, multiplier) {
  return Object.fromEntries(Object.entries(outcomes || {}).map(([key, value]) => (
    [key, Math.round((Number(value) || 0) * multiplier)]
  )));
}

function applyScenario(recordsValue, configValue) {
  const records = (recordsValue || []).map(row => ({ ...row, outcomes: { ...(row.outcomes || {}) } }));
  if (!records.length) throw new Error('scenario requires report records');
  const config = scenarioConfig(configValue);
  if (config.targetPlacementId && !records.some(row => row.placementId === config.targetPlacementId)) {
    throw new Error('target placement is not in this campaign dataset');
  }
  const targetPlacementId = resolveTarget(records, config.targetPlacementId);
  const dates = recentDates(records, config.windowDays * config.persistenceWindows);
  const targetRows = row => row.placementId === targetPlacementId && dates.has(row.date);
  const severityMultiplier = Math.max(0.02, 1 - config.impact);

  const transformed = records.map(original => {
    let row = { ...original, outcomes: { ...original.outcomes } };
    if (config.presetId === 'healthy_baseline' || config.presetId === 'recovery_success') {
      // The immutable baseline is already healthy; recovery success returns to it.
    } else if (config.presetId === 'low_impression_zone' && targetRows(row)) {
      row.impressions *= severityMultiplier;
      row.clicks *= severityMultiplier;
      row.reach *= severityMultiplier;
      row.spend *= severityMultiplier;
      row.conversions *= severityMultiplier;
      row.outcomes = scaleOutcomes(row.outcomes, severityMultiplier);
    } else if (config.presetId === 'low_ctr' && targetRows(row)) {
      row.clicks *= severityMultiplier;
      row.conversions *= severityMultiplier;
      row.outcomes = scaleOutcomes(row.outcomes, severityMultiplier);
    } else if (config.presetId === 'creative_failure' && targetRows(row)) {
      row.impressions *= 0.08;
      row.clicks = 0;
      row.reach *= 0.08;
      row.spend *= 0.08;
      row.conversions = 0;
      row.outcomes = scaleOutcomes(row.outcomes, 0);
    } else if (['click_tracking_failure', 'click_overlay'].includes(config.presetId) && targetRows(row)) {
      row.clicks = 0;
      row.conversions = 0;
      row.outcomes = scaleOutcomes(row.outcomes, 0);
    } else if (config.presetId === 'poor_placement' && targetRows(row)) {
      row.clicks *= Math.max(0.08, severityMultiplier * 0.55);
      row.spend *= 1.15;
      row.conversions *= severityMultiplier;
      row.outcomes = scaleOutcomes(row.outcomes, severityMultiplier);
    } else if (config.presetId === 'tracking_delay' && targetRows(row)) {
      row.conversions = 0;
      row.outcomes = scaleOutcomes(row.outcomes, 0);
    } else if (config.presetId === 'multiple_issues' && targetRows(row)) {
      row.impressions *= severityMultiplier;
      row.clicks *= severityMultiplier * 0.3;
      row.reach *= severityMultiplier;
      row.spend *= 0.85;
      row.conversions = 0;
      row.outcomes = scaleOutcomes(row.outcomes, 0);
    } else if (config.presetId === 'recovery_ineffective' && targetRows(row)) {
      row.impressions *= 0.55;
      // Keep the failed recovery clearly beyond the default CTR z-threshold
      // even after integer rounding of daily facts.
      row.clicks *= 0.30;
      row.reach *= 0.55;
      row.spend *= 0.65;
      row.conversions *= 0.30;
      row.outcomes = scaleOutcomes(row.outcomes, 0.30);
    }
    return derived({
      ...row,
      scenario: {
        presetId: config.presetId,
        targetPlacementId,
        windowDays: config.windowDays,
        persistenceWindows: config.persistenceWindows,
        impact: config.impact,
        seed: config.seed,
        signals: {
          creativeRenderFailure: config.presetId === 'creative_failure' && targetRows(row),
          clickTelemetryFailure: config.presetId === 'click_tracking_failure' && targetRows(row),
          configDrift: config.presetId === 'config_drift',
          trackingDelay: config.presetId === 'tracking_delay' && targetRows(row),
          recoveryAttempted: ['recovery_success', 'recovery_ineffective'].includes(config.presetId),
        },
      },
    });
  });

  const resolved = { ...config, targetPlacementId };
  const { buildRuntimeFixture } = require('./investigationFixtures');
  return { config: resolved, records: transformed,
    runtimeFixture: buildRuntimeFixture(resolved, [...new Set(records.map(row => row.placementId))]) };
}

module.exports = { PRESETS, scenarioConfig, applyScenario, expectationFor };
