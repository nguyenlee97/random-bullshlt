'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { applyScenario } = require('../lib/reportScenarios');

// Exercise the real service with in-memory model adapters; no Mongo or model API calls.
function harness(t) {
  const rows = ['2026-08-01', '2026-08-02', '2026-08-03'].map(date => ({
    campaignId: 'ORD-TEST', placementId: 'zone-a', date, impressions: 1000,
    clicks: 20, spend: 100000, reach: 800, conversions: 3, outcomes: {},
  }));
  const datasets = [{ campaignId: 'ORD-TEST', kind: 'baseline', revision: 1,
    inputHash: 'base', input: { campaignId: 'ORD-TEST', inputHash: 'base' }, records: rows }];
  const states = [{ campaignId: 'ORD-TEST', activeRevision: 1, nextRevision: 1 }];
  const legacyAnalyses = [{ campaignId: 'ORD-TEST', overall: 'baseline' }];
  const control = { failBuild: false, failAfterPublish: false, calls: 0, gate: null };
  const copy = value => value == null ? value : structuredClone(value);
  const get = (o, key) => key.split('.').reduce((v, k) => v?.[k], o);
  function matches(doc, query) {
    return Object.entries(query).every(([key, value]) => {
      if (key === '$or') return value.some(q => matches(doc, q));
      const actual = get(doc, key);
      if (value && typeof value === 'object' && !(value instanceof Date)) {
        return Object.entries(value).every(([op, expected]) => (
          op === '$exists' ? (actual !== undefined) === expected
          : op === '$lte' ? actual <= expected : op === '$gt' ? actual > expected
          : op === '$ne' ? actual !== expected : op === '$eq' ? actual === expected
          : op === '$in' ? expected.includes(actual) : op === '$nin' ? !expected.includes(actual) : false));
      }
      return actual === value;
    });
  }
  function update(doc, changes) {
    for (const [op, fields] of Object.entries(changes)) for (const [key, value] of Object.entries(fields)) {
      const parts = key.split('.'); let target = doc;
      for (const part of parts.slice(0, -1)) target = target[part] ||= {};
      const last = parts.at(-1);
      if (op === '$set') target[last] = copy(value);
      else if (op === '$unset') delete target[last];
      else if (op === '$inc') target[last] = (target[last] || 0) + value;
    }
  }
  function query(value) {
    return { lean: async () => copy(value), then: (yes, no) => Promise.resolve(copy(value)).then(yes, no),
      sort() { return this; }, limit() { return this; } };
  }
  function model(items) {
    return {
      findOne: q => query(items.find(d => matches(d, q)) || null),
      find: q => query(items.filter(d => matches(d, q))),
      findOneAndUpdate(q, changes) {
        const doc = items.find(d => matches(d, q));
        if (doc) update(doc, changes);
        return query(doc || null);
      },
      async updateOne(q, changes) {
        if (control.failAfterPublish && changes.$set?.status === 'published') {
          control.failAfterPublish = false;
          throw new Error('acknowledgement lost after pointer publication');
        }
        const doc = items.find(d => matches(d, q));
        if (doc) update(doc, changes);
        return { modifiedCount: doc ? 1 : 0 };
      },
      async create(value) { items.push(copy(value)); return { toObject: () => copy(value) }; },
    };
  }
  const replacements = {
    '../models/ReportDataset': model(datasets),
    '../models/CampaignReportState': model(states),
    '../models/AnalyticsRecord': model(rows),
    '../models/ReportAnalysis': model(legacyAnalyses),
    '../services/reportGenerator': {
      REPORT_TYPES: ['executive', 'delivery', 'creative', 'audience', 'cost', 'conversion'],
      async generateAnalysis(input, records, reportType) {
        control.calls++;
        if (control.gate) await control.gate;
        if (control.failBuild) throw new Error('analysis unavailable');
        return { overall: reportType, dataContract: { contractVersion: 'v2', inputHash: input.inputHash } };
      },
      questionsForReport: () => [],
    },
  };
  const saved = [];
  for (const [name, exports] of Object.entries(replacements)) {
    const id = require.resolve(name); saved.push([id, require.cache[id]]);
    require.cache[id] = { id, filename: id, loaded: true, exports };
  }
  const id = require.resolve('../services/reportDatasets');
  saved.push([id, require.cache[id]]); delete require.cache[id];
  const service = require(id);
  t.after(() => { for (const [key, value] of saved) { if (value) require.cache[key] = value; else delete require.cache[key]; } });
  return { service, datasets, states, control, rows, legacyAnalyses,
    config: { presetId: 'low_ctr', requestId: 'request_0001', expectedRevision: 1 } };
}

test('apply publishes six analyses and facts together; replay does not rebuild', async t => {
  const h = harness(t);
  const first = await h.service.applyScenarioRevision('ORD-TEST', h.config);
  const snapshot = await h.service.activeSnapshot('ORD-TEST');
  assert.equal(first.revision, 2);
  assert.deepEqual(first.expectation.l1IssueTypes, ['ctr_regression']);
  assert.ok(first.expectation.requiredEvidence.includes('metrics_window'));
  assert.equal(snapshot.analyses.length, 6);
  assert.ok(snapshot.analyses.every(a => a.inputHash === snapshot.inputHash));
  assert.deepEqual(snapshot.records.map(r => r.clicks), applyScenario(h.rows, h.config).records.map(r => r.clicks));
  const again = await h.service.applyScenarioRevision('ORD-TEST', h.config);
  assert.equal(again.replayed, true);
  assert.equal(h.datasets.length, 2);
  assert.equal(h.control.calls, 6);
  assert.equal(h.states[0].leaseToken, undefined);
});

test('runtime evidence is published on the same immutable scenario revision', async t => {
  const h = harness(t);
  const result = await h.service.applyScenarioRevision('ORD-TEST', { ...h.config, presetId: 'click_overlay' });
  const snapshot = await h.service.activeSnapshot('ORD-TEST');
  assert.equal(snapshot.revision, result.revision);
  assert.match(snapshot.runtimeFixture.pages['zone-a'], /pointer-events:auto/);
  assert.equal(snapshot.analyses.length, 6);
  const original = structuredClone(snapshot.runtimeFixture);
  await h.service.applyScenarioRevision('ORD-TEST', { ...h.config, presetId: 'healthy_baseline', requestId: 'request_0002', expectedRevision: 2 });
  assert.deepEqual(h.datasets.find(d => d.revision === 2).runtimeFixture, original);
  assert.match((await h.service.activeSnapshot('ORD-TEST')).runtimeFixture.pages['zone-a'], /pointer-events:none/);
});

test('failed build leaves active data untouched and same request resumes its revision', async t => {
  const h = harness(t);
  h.control.failBuild = true;
  await assert.rejects(h.service.applyScenarioRevision('ORD-TEST', h.config), /analysis unavailable/);
  assert.equal(h.states[0].activeRevision, 1);
  assert.deepEqual(await h.service.activeRecords('ORD-TEST'), h.rows);
  assert.equal(h.states[0].leaseToken, undefined);
  h.control.failBuild = false;
  assert.equal((await h.service.applyScenarioRevision('ORD-TEST', h.config)).revision, 2);
  assert.equal(h.datasets.length, 2);
});

test('commit-then-timeout retry returns the already published revision', async t => {
  const h = harness(t);
  h.control.failAfterPublish = true;
  await assert.rejects(h.service.applyScenarioRevision('ORD-TEST', h.config), /acknowledgement lost/);
  assert.equal(h.states[0].activeRevision, 2);
  assert.equal((await h.service.activeSnapshot('ORD-TEST')).analyses.length, 6);
  const again = await h.service.applyScenarioRevision('ORD-TEST', h.config);
  assert.equal(again.replayed, true);
  assert.equal(h.control.calls, 6);
});

test('stale revision, changed payload and invalid placement reject without new dataset', async t => {
  const h = harness(t);
  await h.service.applyScenarioRevision('ORD-TEST', h.config);
  for (const changes of [{ requestId: 'request_0002' }, { impact: 0.2 }]) {
    await assert.rejects(h.service.applyScenarioRevision('ORD-TEST', { ...h.config, ...changes }), e => e.status === 409);
  }
  await assert.rejects(h.service.applyScenarioRevision('ORD-TEST', {
    ...h.config, requestId: 'request_0003', expectedRevision: 2, targetPlacementId: 'unknown',
  }), /placement/i);
  assert.equal(h.datasets.length, 2);
});

test('concurrent apply cannot publish a competing revision while first build holds lease', async t => {
  const h = harness(t); let release;
  h.control.gate = new Promise(resolve => { release = resolve; });
  const first = h.service.applyScenarioRevision('ORD-TEST', h.config);
  while (!h.control.calls) await new Promise(resolve => setImmediate(resolve));
  assert.equal(await h.service.activeSnapshot('ORD-TEST'), null);
  await assert.rejects(h.service.applyScenarioRevision('ORD-TEST', { ...h.config, requestId: 'request_0002' }), e => e.status === 409);
  release();
  await first;
  assert.equal(h.datasets.length, 2);
});

test('reset creates a new baseline-derived snapshot; older replay never moves active pointer', async t => {
  const h = harness(t);
  await h.service.applyScenarioRevision('ORD-TEST', h.config);
  const reset = await h.service.applyScenarioRevision('ORD-TEST', {
    presetId: 'healthy_baseline', requestId: 'request_reset', expectedRevision: 2,
  });
  assert.equal(reset.revision, 3);
  assert.deepEqual((await h.service.activeRecords('ORD-TEST')).map(r => r.clicks), h.rows.map(r => r.clicks));
  assert.equal((await h.service.applyScenarioRevision('ORD-TEST', h.config)).revision, 2);
  assert.equal(h.states[0].activeRevision, 3);
});

test('Analytics aggregate and campaign reads overlay the active snapshot exactly once', async t => {
  const h = harness(t);
  await h.service.applyScenarioRevision('ORD-TEST', h.config);
  const id = require.resolve('../routes/analytics'), saved = require.cache[id];
  delete require.cache[id];
  const router = require(id);
  t.after(() => { if (saved) require.cache[id] = saved; else delete require.cache[id]; });
  async function request(path, query = {}) {
    let value, status = 200;
    const res = { set() {}, status(code) { status = code; return this; }, json(data) { value = data; } };
    await router.stack.find(layer => layer.route?.path === path).route.stack[0].handle({ query }, res);
    assert.equal(status, 200);
    return value;
  }
  const expected = await h.service.activeRecords('ORD-TEST');
  const all = await request('/data');
  const campaign = await request('/data', { campaignId: 'ORD-TEST' });
  assert.equal(all.length, expected.length);
  assert.deepEqual(all, campaign);
  assert.equal((await request('/summary')).totalClicks, expected.reduce((sum, r) => sum + r.clicks, 0));
  assert.equal((await request('/by-campaign'))[0].clicks, expected.reduce((sum, r) => sum + r.clicks, 0));
  assert.equal((await request('/data', { campaignId: 'OTHER' })).length, 0);
  assert.equal((await request('/data', { startDate: '2026-08-03' })).length, 1);
});

test('legacy scenario prose migrates only with six matching input hashes', async t => {
  const h = harness(t);
  h.states[0].activeRevision = 2;
  h.datasets.push({ ...structuredClone(h.datasets[0]), kind: 'scenario', revision: 2, inputHash: 'legacy-scenario' });
  await assert.rejects(h.service.activeRecords('ORD-TEST'), e => e.status === 409);
  h.legacyAnalyses.splice(0, h.legacyAnalyses.length,
    ...Array.from({ length: 6 }, (_, i) => ({ campaignId: 'ORD-TEST', inputHash: 'legacy-scenario',
      status: 'ready', reportType: 'type-' + i })));
  const snapshot = await h.service.activeSnapshot('ORD-TEST');
  assert.equal(snapshot.analyses.length, 6);
  h.legacyAnalyses.splice(0); // the published copy no longer depends on mutable legacy prose
  assert.equal((await h.service.activeSnapshot('ORD-TEST')).analyses.length, 6);
});

test('missing active snapshot fails closed instead of showing unrelated legacy facts', async t => {
  const h = harness(t);
  h.states[0].activeRevision = 99;
  await assert.rejects(h.service.activeRecords('ORD-TEST'), e => e.status === 409);
  await assert.rejects(h.service.activeAnalyses('ORD-TEST'), e => e.status === 409);
});
