'use strict';

const crypto = require('node:crypto');

const OBJECTIVES = new Set(['awareness', 'consideration', 'conversion', 'retention']);
const DAY_MS = 24 * 60 * 60 * 1000;

const EVENT_LIBRARY = Object.freeze({
  viewable_impression: { label: 'Viewable impression', stage: 'media_quality', baseRate: 0.78 },
  completed_view: { label: 'Completed view', stage: 'engagement', baseRate: 0.34 },
  engaged_visit: { label: 'Engaged visit', stage: 'engagement', baseRate: 0.62 },
  product_view: { label: 'Product view', stage: 'consideration', baseRate: 0.72 },
  add_to_cart: { label: 'Add to cart', stage: 'intent', baseRate: 0.16 },
  checkout: { label: 'Checkout', stage: 'intent', baseRate: 0.48 },
  test_ride_registration: { label: 'Đăng ký lái thử', stage: 'lead', baseRate: 0.032 },
  qualified_test_ride: { label: 'Đăng ký lái thử đủ điều kiện', stage: 'qualified_lead', baseRate: 0.86 },
  attended_test_ride: { label: 'Khách đến lái thử', stage: 'offline_action', baseRate: 0.68 },
  lead: { label: 'Lead', stage: 'lead', baseRate: 0.035 },
  qualified_lead: { label: 'Qualified lead', stage: 'qualified_lead', baseRate: 0.58 },
  sales_accepted_lead: { label: 'Sales accepted lead', stage: 'sales', baseRate: 0.7 },
  trial_started: { label: 'Trial started', stage: 'trial', baseRate: 0.025 },
  activated: { label: 'Activated user', stage: 'activation', baseRate: 0.62 },
  subscribed: { label: 'Subscribed user', stage: 'purchase', baseRate: 0.28 },
  re_engagement: { label: 'Re-engaged user', stage: 'retention', baseRate: 0.024 },
  retained_30d: { label: 'Retained user (30 ngày)', stage: 'retention', baseRate: 0.55 },
  conversion: { label: 'Conversion', stage: 'conversion', baseRate: 0.03 },
  deposit: { label: 'Đặt cọc', stage: 'deposit', baseRate: 0.23 },
  purchase: { label: 'Purchase', stage: 'purchase', baseRate: 0.7 },
});

function fold(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (!value || typeof value !== 'object') return value;
  return Object.keys(value).sort().reduce((result, key) => {
    if (value[key] !== undefined) result[key] = stable(value[key]);
    return result;
  }, {});
}

function stableStringify(value) {
  return JSON.stringify(stable(value));
}

function dateOnly(value, fallback) {
  const text = String(value || fallback || '').slice(0, 10);
  const parsed = new Date(`${text}T00:00:00.000Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text) || Number.isNaN(parsed.getTime())) {
    throw new Error(`invalid report date: ${value || fallback || 'empty'}`);
  }
  return text;
}

function addDays(value, days) {
  const date = new Date(`${value}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function normalizeZones(rawZones) {
  const seen = new Set();
  const zones = [];
  for (const [index, item] of (Array.isArray(rawZones) ? rawZones : []).entries()) {
    const value = typeof item === 'string' ? { id: item } : (item || {});
    const id = String(value.id || value.placementId || `zone_${index + 1}`).trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    zones.push({
      id,
      channel: String(value.channel || value.platform || 'Zalo'),
      format: String(value.format || value.size || 'banner'),
      cpm: Math.max(1, Math.round(Number(value.cpm) || 45_000)),
      reach: Math.max(0, Math.round(Number(value.reach) || 0)),
      weight: Number.isFinite(Number(value.weight)) ? Math.max(Number(value.weight), 0) : null,
    });
  }
  return zones.length ? zones : [{
    id: 'znews_homepage_banner', channel: 'Znews', format: 'banner',
    cpm: 45_000, reach: 0, weight: null,
  }];
}

function normalizeReportInput(raw = {}) {
  const brief = raw.brief && typeof raw.brief === 'object' ? raw.brief : {};
  const startDate = dateOnly(raw.startDate || brief.startDate, new Date().toISOString().slice(0, 10));
  const legacyEndDate = addDays(startDate, 13);
  const endDate = dateOnly(raw.endDate || brief.endDate, legacyEndDate);
  const durationDays = Math.floor((new Date(`${endDate}T00:00:00Z`) - new Date(`${startDate}T00:00:00Z`)) / DAY_MS) + 1;
  if (durationDays < 1 || durationDays > 366) {
    throw new Error(`report duration must be between 1 and 366 days; received ${durationDays}`);
  }
  const objective = OBJECTIVES.has(String(raw.objective || brief.objective).toLowerCase())
    ? String(raw.objective || brief.objective).toLowerCase()
    : 'awareness';
  const budget = Math.max(0, Math.round(Number(raw.budget ?? brief.budget) || 0));
  const normalized = {
    contractVersion: 'report-input-v2',
    campaignId: String(raw.campaignId || brief.campaignId || 'campaign').trim(),
    brand: String(raw.brand || brief.brand || 'Unknown Brand').trim(),
    objective,
    budget,
    startDate,
    endDate,
    durationDays,
    kpi: String(raw.kpi || brief.kpi || '').trim(),
    notes: String(raw.notes || brief.notes || '').trim(),
    zones: normalizeZones(raw.zones),
    audience: Array.isArray(raw.audience) ? raw.audience : [],
    geo: Array.isArray(raw.geo) ? raw.geo : (raw.geo ? [raw.geo] : []),
    strategy: raw.strategy && typeof raw.strategy === 'object' ? raw.strategy : null,
    forecast: raw.forecast && typeof raw.forecast === 'object' ? raw.forecast : null,
    targeting: raw.targeting && typeof raw.targeting === 'object' ? raw.targeting : null,
    creative: raw.creative && typeof raw.creative === 'object' ? raw.creative : null,
    measurementSpec: raw.measurementSpec && typeof raw.measurementSpec === 'object'
      ? raw.measurementSpec : null,
  };
  normalized.inputHash = crypto.createHash('sha256')
    .update(stableStringify(normalized))
    .digest('hex');
  return normalized;
}

function event(id) {
  return { id, ...EVENT_LIBRARY[id] };
}

function includesAny(text, values) {
  return values.some(value => text.includes(value));
}

function inferOutcomeEventIds(input) {
  const text = fold(`${input.kpi}\n${input.notes}`);
  if (includesAny(text, ['lai thu', 'test ride'])) {
    const ids = ['test_ride_registration'];
    if (includesAny(text, ['du dieu kien', 'qualified'])) ids.push('qualified_test_ride');
    if (includesAny(text, ['den lai thu', 'tham gia lai thu', 'attend'])) ids.push('attended_test_ride');
    if (includesAny(text, ['dat coc', 'deposit'])) ids.push('deposit');
    if (includesAny(text, ['mua xe', 'purchase', 'purchased'])) ids.push('purchase');
    return ids;
  }
  if (includesAny(text, ['add to cart', 'gio hang', 'checkout', 'don hang', 'order', 'purchase', 'purchased'])) {
    const ids = ['product_view'];
    if (includesAny(text, ['gio hang', 'add to cart'])) ids.push('add_to_cart');
    if (text.includes('checkout')) ids.push('checkout');
    ids.push('purchase');
    return [...new Set(ids)];
  }
  if (includesAny(text, ['trial', 'dung thu', 'subscription', 'subscribe', 'dang ky goi'])) {
    return ['trial_started', 'activated', 'subscribed'];
  }
  if (includesAny(text, ['qualified lead', 'lead du dieu kien', 'sales accepted'])) {
    return ['lead', 'qualified_lead', 'sales_accepted_lead'];
  }
  if (input.objective === 'awareness') return ['viewable_impression', 'completed_view'];
  if (input.objective === 'consideration') return ['engaged_visit', 'product_view'];
  if (input.objective === 'retention') return ['re_engagement', 'retained_30d'];
  if (includesAny(text, ['lead', 'dang ky', 'form'])) return ['lead', 'qualified_lead'];
  return ['conversion'];
}

function parseNumber(raw) {
  const token = String(raw || '').trim();
  if (!token) return null;
  const compact = token.replace(/\s/g, '');
  let multiplier = 1;
  if (/trieu|million/i.test(fold(compact))) multiplier = 1_000_000;
  else if (/nghin|ngan|thousand|k$/i.test(fold(compact))) multiplier = 1_000;
  const numeric = compact
    .replace(/(?:vnd|vnđ|dong|đ|trieu|million|nghin|ngan|thousand|k)/gi, '')
    .replace(/[.,](?=\d{3}(?:\D|$))/g, '')
    .replace(',', '.');
  const value = Number(numeric);
  return Number.isFinite(value) ? value * multiplier : null;
}

function eventForClause(clause, ids) {
  const text = fold(clause);
  const rules = [
    ['qualified_test_ride', ['dang ky lai thu du dieu kien', 'du dieu kien']],
    ['attended_test_ride', ['khach den lai thu', 'den lai thu', 'attend']],
    ['deposit', ['dat coc', 'deposit']],
    ['purchase', ['mua xe', 'don hang', 'purchase', 'purchased']],
    ['test_ride_registration', ['dang ky lai thu', 'lai thu']],
    ['qualified_lead', ['qualified lead', 'lead du dieu kien']],
    ['sales_accepted_lead', ['sales accepted']],
    ['lead', ['lead', 'dang ky form']],
    ['subscribed', ['subscription', 'subscribe', 'dang ky goi']],
    ['activated', ['activated', 'kich hoat']],
    ['trial_started', ['trial', 'dung thu']],
    ['retained_30d', ['retained', 'duy tri 30']],
    ['re_engagement', ['re-engagement', 'tai tuong tac']],
    ['completed_view', ['completed view', 'hoan tat video']],
    ['viewable_impression', ['viewability', 'viewable']],
  ];
  for (const [id, markers] of rules) {
    if (ids.includes(id) && includesAny(text, markers)) return id;
  }
  return ids.at(-1);
}

function numericTokens(clause) {
  const matches = String(clause).match(/\d[\d.,]*(?:(?:\s*(?:triệu|trieu|million|nghìn|nghin|ngàn|ngan|thousand)\b)|(?:\s*[kK](?=\s|$|[.,])))?/gi) || [];
  return matches.map(parseNumber).filter(Number.isFinite);
}

function buildKpis(input, ids) {
  const raw = `${input.kpi || ''}\n${input.notes || ''}`;
  const clauses = raw.split(/\n|(?<=[!?])\s+|(?<=\.)\s+(?=[A-ZÀ-Ỹ])/u).map(item => item.trim()).filter(Boolean);
  const results = [];
  for (const clause of clauses) {
    const text = fold(clause);
    const numbers = numericTokens(clause);
    if (!numbers.length) continue;
    const eventId = eventForClause(clause, ids);
    const isCost = /\b(cpl|cpa|cpd)\b/.test(text) || includesAny(text, ['chi phi tren moi', 'cost per']);
    const isRate = /%/.test(clause) || includesAny(text, ['ty le', 'rate']);
    const isTarget = includesAny(text, ['toi thieu', 'it nhat', 'khong vuot qua', 'khong qua', 'toi da', 'muc tieu', 'target', 'minimum', 'maximum']);
    if (!isCost && !isRate && !isTarget) continue;
    const operator = includesAny(text, ['khong vuot qua', 'khong qua', 'toi da', 'maximum', 'max ']) ? '<=' : '>=';
    const target = numbers[0];
    const windowMatch = text.match(/(?:trong vong|within)\s*(\d+)\s*ngay/);
    const windowDays = windowMatch ? Number(windowMatch[1]) : null;
    if (isRate) {
      const numeratorEvent = eventId;
      const eventIndex = ids.indexOf(numeratorEvent);
      const denominatorEvent = ids[Math.max(0, eventIndex - 1)] || ids[0];
      results.push({
        id: `rate_${numeratorEvent}`,
        label: `Tỷ lệ ${EVENT_LIBRARY[numeratorEvent]?.label || numeratorEvent}`,
        metric: 'event_rate', numeratorEvent, denominatorEvent,
        operator, target, unit: 'percent', windowDays,
        source: 'brief', sourceText: clause,
      });
    } else if (isCost) {
      let denominatorEvent = eventId;
      if (/\bcpl\b/.test(text) && ids.includes('qualified_test_ride')) denominatorEvent = 'qualified_test_ride';
      results.push({
        id: `cost_per_${denominatorEvent}`,
        label: `Chi phí / ${EVENT_LIBRARY[denominatorEvent]?.label || denominatorEvent}`,
        metric: 'cost_per_event', eventId: denominatorEvent,
        operator: '<=', target, unit: 'VND', windowDays,
        source: 'brief', sourceText: clause,
      });
    } else {
      results.push({
        id: `count_${eventId}`,
        label: EVENT_LIBRARY[eventId]?.label || eventId,
        metric: 'event_count', eventId,
        operator, target, unit: 'count', windowDays,
        source: 'brief', sourceText: clause,
      });
    }
  }
  const deduped = new Map();
  for (const item of results) deduped.set(item.id, item);
  return [...deduped.values()];
}

function buildMeasurementSpec(inputValue) {
  const input = inputValue?.contractVersion === 'report-input-v2'
    ? inputValue : normalizeReportInput(inputValue);
  if (input.measurementSpec?.version === 'measurement-spec-v2') return input.measurementSpec;
  const eventIds = inferOutcomeEventIds(input);
  const events = eventIds.map(event);
  const transitions = events.slice(1).map((item, index) => ({
    from: events[index].id,
    to: item.id,
    expectedRate: item.baseRate,
  }));
  const kpis = buildKpis(input, eventIds);
  return {
    version: 'measurement-spec-v2',
    objective: input.objective,
    optimizationEvent: eventIds[0],
    primaryOutcome: eventIds.at(-1),
    outcomeGraph: { events, transitions },
    kpis,
    dimensions: ['date', 'placementId', 'channel', 'format'],
    attribution: {
      clickWindowDays: input.objective === 'conversion' ? 7 : 1,
      viewWindowDays: 1,
      maxOutcomeLagDays: Math.max(0, ...kpis.map(item => item.windowDays || 0)),
    },
    assumptions: {
      source: 'brief_and_objective_rules',
      deterministic: true,
      inputHash: input.inputHash,
    },
  };
}

module.exports = {
  EVENT_LIBRARY,
  normalizeReportInput,
  buildMeasurementSpec,
  stableStringify,
  fold,
  parseNumber,
};
