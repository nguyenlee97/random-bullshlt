'use strict';

const crypto = require('node:crypto');
const { normalizeReportInput, buildMeasurementSpec } = require('./reportMeasurement');

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round((Number(value) || 0) * factor) / factor;
}

function seedFrom(value) {
  return Number.parseInt(crypto.createHash('sha256').update(String(value)).digest('hex').slice(0, 8), 16) >>> 0;
}

function mulberry32(seed) {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function datesBetween(startDate, durationDays) {
  const start = new Date(`${startDate}T00:00:00.000Z`);
  return Array.from({ length: durationDays }, (_, index) => {
    const value = new Date(start);
    value.setUTCDate(value.getUTCDate() + index);
    return value.toISOString().slice(0, 10);
  });
}

function phaseFor(index, duration) {
  const progress = duration <= 1 ? 1 : index / (duration - 1);
  if (progress < 0.12) return 'ramp';
  if (progress > 0.78) return 'fatigue';
  return 'stable';
}

function phaseFactor(phase) {
  if (phase === 'ramp') return 0.82;
  if (phase === 'fatigue') return 0.93;
  return 1.05;
}

function distributeInteger(total, weightedCells) {
  if (!weightedCells.length || total <= 0) return weightedCells.map(() => 0);
  const sumWeight = weightedCells.reduce((sum, cell) => sum + cell.weight, 0) || weightedCells.length;
  const raw = weightedCells.map(cell => total * (cell.weight || 1) / sumWeight);
  const values = raw.map(Math.floor);
  let remainder = total - values.reduce((sum, value) => sum + value, 0);
  const order = raw.map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((a, b) => b.fraction - a.fraction || a.index - b.index);
  for (let index = 0; index < remainder; index += 1) values[order[index % order.length].index] += 1;
  return values;
}

function firstEventCount(event, { impressions, clicks, vi }) {
  if (event.id === 'viewable_impression') return Math.min(impressions, Math.round(impressions * vi / 100));
  if (event.id === 'completed_view') return Math.round(impressions * event.baseRate);
  return Math.min(clicks, Math.round(clicks * event.baseRate));
}

function simulateOutcomes(spec, media, factor) {
  const outcomes = {};
  const events = spec.outcomeGraph?.events || [];
  if (!events.length) return outcomes;
  outcomes[events[0].id] = firstEventCount(events[0], media);
  for (let index = 1; index < events.length; index += 1) {
    const previous = events[index - 1];
    const current = events[index];
    const transition = spec.outcomeGraph.transitions?.find(item => (
      item.from === previous.id && item.to === current.id
    ));
    const rate = Math.max(0.01, Math.min(0.98, (transition?.expectedRate ?? current.baseRate ?? 0.5) * factor));
    outcomes[current.id] = Math.min(outcomes[previous.id], Math.round(outcomes[previous.id] * rate));
  }
  return outcomes;
}

function simulateReportFacts(inputValue, measurementValue) {
  const input = inputValue?.contractVersion === 'report-input-v2'
    ? inputValue : normalizeReportInput(inputValue);
  const measurement = measurementValue?.version === 'measurement-spec-v2'
    ? measurementValue : buildMeasurementSpec(input);
  const dates = datesBetween(input.startDate, input.durationDays);
  const seed = seedFrom(`${input.inputHash}:report-facts-v2`);
  const random = mulberry32(seed);
  const cells = [];
  for (const [dayIndex, date] of dates.entries()) {
    const day = new Date(`${date}T00:00:00Z`).getUTCDay();
    const weekdayFactor = day === 0 || day === 6 ? 0.82 : 1.06;
    const phase = phaseFor(dayIndex, dates.length);
    for (const [zoneIndex, zone] of input.zones.entries()) {
      const zoneWeight = zone.weight ?? (1 + ((seedFrom(zone.id) % 31) - 15) / 100);
      cells.push({
        date, dayIndex, zoneIndex, zone, phase,
        weight: Math.max(0.1, zoneWeight * weekdayFactor * phaseFactor(phase) * (0.96 + random() * 0.08)),
      });
    }
  }

  const targetSpend = Math.max(0, Math.round(input.budget * 0.85));
  const spends = distributeInteger(targetSpend, cells);
  const objectiveCtr = {
    awareness: 0.0055, consideration: 0.009, conversion: 0.011,
    retention: 0.008,
  }[input.objective] || 0.007;
  const forecastCpm = Number(
    input.forecast?.averageCpm || input.forecast?.average_cpm || 0
  );
  const selectedStrategy = input.strategy?.selected || 'balanced';
  const strategyCtrFactor = selectedStrategy === 'quality_first' ? 1.12
    : selectedStrategy === 'reach_first' ? 0.92 : 1;
  const frequency = Math.max(1.2, Number(
    input.forecast?.frequency || input.strategy?.frequency || 2.8
  ));

  const rows = cells.map((cell, index) => {
    const { zone, phase } = cell;
    const zoneSignal = ((seedFrom(zone.id) % 29) - 14) / 100;
    const phaseCtrFactor = phase === 'ramp' ? 0.92 : phase === 'fatigue' ? 0.84 : 1.06;
    const cpmBase = zone.cpm || forecastCpm || 45_000;
    const cpm = Math.max(1, round(cpmBase * (0.96 + cell.dayIndex % 5 * 0.018 + zoneSignal * 0.12), 0));
    const spend = spends[index];
    const impressions = Math.max(0, Math.round(spend / cpm * 1000));
    const ctrRate = Math.max(0.001, objectiveCtr * strategyCtrFactor * phaseCtrFactor * (1 + zoneSignal));
    const clicks = Math.min(impressions, Math.round(impressions * ctrRate));
    const viBase = /video/i.test(zone.format) ? 74 : /native/i.test(zone.format) ? 79 : 76;
    const vi = round(Math.max(50, Math.min(95, viBase + zoneSignal * 35 + (phase === 'stable' ? 2 : -1))), 1);
    const reach = Math.min(impressions, Math.round(impressions / Math.max(1, frequency * 0.42)));
    const transitionFactor = Math.max(0.82, Math.min(1.12,
      (phase === 'fatigue' ? 0.9 : phase === 'ramp' ? 0.95 : 1.04) * (1 + zoneSignal * 0.25)
    ));
    const media = { impressions, clicks, vi };
    const outcomes = simulateOutcomes(measurement, media, transitionFactor);
    return {
      campaignId: input.campaignId,
      placementId: zone.id,
      date: cell.date,
      channel: zone.channel,
      format: zone.format,
      impressions,
      clicks,
      spend,
      ctr: round(impressions ? clicks / impressions * 100 : 0),
      cpm: round(impressions ? spend / impressions * 1000 : 0),
      reach,
      conversions: Number(outcomes[measurement.optimizationEvent] || 0),
      vi,
      outcomes,
      scenario: { phase, seedVersion: 'report-facts-v2' },
      source: 'scenario_simulation',
      inputHash: input.inputHash,
    };
  });
  validateReportFacts(input, measurement, rows);
  return rows;
}

function validateReportFacts(inputValue, measurementValue, rows) {
  const input = inputValue?.contractVersion === 'report-input-v2'
    ? inputValue : normalizeReportInput(inputValue);
  const measurement = measurementValue?.version === 'measurement-spec-v2'
    ? measurementValue : buildMeasurementSpec(input);
  const expected = input.durationDays * input.zones.length;
  if (!Array.isArray(rows) || rows.length !== expected) {
    throw new Error(`report fact matrix mismatch: expected ${expected}, received ${rows?.length || 0}`);
  }
  const cells = new Set();
  let spend = 0;
  for (const row of rows) {
    const key = `${row.date}:${row.placementId}`;
    if (cells.has(key)) throw new Error(`duplicate report fact cell: ${key}`);
    cells.add(key);
    spend += Number(row.spend) || 0;
    const expectedCtr = row.impressions ? row.clicks / row.impressions * 100 : 0;
    const expectedCpm = row.impressions ? row.spend / row.impressions * 1000 : 0;
    if (Math.abs(expectedCtr - row.ctr) > 0.002) throw new Error(`invalid CTR formula at ${key}`);
    if (Math.abs(expectedCpm - row.cpm) > 0.002) throw new Error(`invalid CPM formula at ${key}`);
    let parent = Number.POSITIVE_INFINITY;
    for (const event of measurement.outcomeGraph?.events || []) {
      const value = Number(row.outcomes?.[event.id] || 0);
      if (!Number.isInteger(value) || value < 0 || value > parent) {
        throw new Error(`invalid outcome funnel at ${key}:${event.id}`);
      }
      parent = value;
    }
  }
  if (spend > input.budget) throw new Error(`report spend exceeds budget: ${spend} > ${input.budget}`);
  return { rowCount: rows.length, spend, inputHash: input.inputHash };
}

module.exports = {
  simulateReportFacts,
  validateReportFacts,
  datesBetween,
  seedFrom,
};
