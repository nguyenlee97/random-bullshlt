'use strict';

const ESTIMATE_VERSION = 'vn-catalog-v1';

// Ranges represent plausible addressable users for a Vietnam campaign demo.
// They are used only when the imported catalog has no publisher-provided size.
const CATEGORY_RANGES = {
  'Behavior|Expats': [90_000, 750_000],
  'Interest|Entertainment (leisure)': [650_000, 8_500_000],
  'Interest|Fitness and wellness (fitness)': [450_000, 4_500_000],
  'Interest|Food and drink (consumables)': [300_000, 7_000_000],
  'Interest|Technology (computers & electronics)': [500_000, 8_000_000],
};

const TYPE_RANGES = {
  Behavior: [250_000, 12_000_000],
  Interest: [350_000, 9_000_000],
};

function stableUnit(seed) {
  let hash = 2166136261;
  for (const char of String(seed || 'audience')) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 0xffffffff;
}

function roundAudience(value) {
  const step = value >= 1_000_000 ? 10_000 : 1_000;
  return Math.max(step, Math.round(value / step) * step);
}

function formatAudience(value) {
  return Number(value || 0).toLocaleString('vi-VN');
}

function hasCatalogSize(segment = {}) {
  return Number(segment.sizeMin || 0) > 0 || Number(segment.sizeMax || 0) > 0;
}

function audienceSizeEstimate(segment = {}) {
  const key = `${segment.type || ''}|${segment.category || ''}`;
  const [floor, ceiling] = CATEGORY_RANGES[key]
    || TYPE_RANGES[segment.type]
    || [300_000, 8_000_000];
  const identity = segment.segmentId || segment.fullLabel || segment.name || key;
  const centerRatio = 0.12 + stableUnit(`${identity}:center`) * 0.76;
  const spreadRatio = 0.10 + stableUnit(`${identity}:spread`) * 0.09;
  const center = floor + (ceiling - floor) * centerRatio;
  const sizeMin = roundAudience(center * (1 - spreadRatio));
  const sizeMax = Math.max(sizeMin + 1_000, roundAudience(center * (1 + spreadRatio)));

  return {
    sizeMin,
    sizeMax,
    sizeRaw: `${formatAudience(sizeMin)} - ${formatAudience(sizeMax)}`,
    sizeSource: 'modeled_estimate',
    sizeEstimateVersion: ESTIMATE_VERSION,
  };
}

function withAudienceSizeEstimate(segment = {}) {
  if (hasCatalogSize(segment)) {
    return {
      ...segment,
      sizeSource: segment.sizeSource || 'catalog',
    };
  }
  return { ...segment, ...audienceSizeEstimate(segment) };
}

module.exports = {
  ESTIMATE_VERSION,
  audienceSizeEstimate,
  hasCatalogSize,
  withAudienceSizeEstimate,
};
