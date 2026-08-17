const test = require('node:test');
const assert = require('node:assert/strict');

const {
  DEFAULT_REPORT_GENERATION_LEASE_MS,
  reportGenerationLeaseMs,
  hasActiveReportGeneration,
} = require('../lib/reportGenerationLease');

test('a recent generating report holds the generation lease', () => {
  const nowMs = Date.parse('2026-08-17T10:00:00.000Z');
  const docs = [{ status: 'generating', updatedAt: new Date(nowMs - 60_000) }];
  assert.equal(hasActiveReportGeneration(docs, { nowMs }), true);
});

test('a stale generating report can be reclaimed after a restart', () => {
  const nowMs = Date.parse('2026-08-17T10:00:00.000Z');
  const docs = [{
    status: 'generating',
    updatedAt: new Date(nowMs - DEFAULT_REPORT_GENERATION_LEASE_MS - 1),
  }];
  assert.equal(hasActiveReportGeneration(docs, { nowMs }), false);
});

test('ready and error reports do not hold the lease', () => {
  const updatedAt = new Date();
  assert.equal(hasActiveReportGeneration([
    { status: 'ready', updatedAt },
    { status: 'error', updatedAt },
  ]), false);
});

test('lease duration can be configured and invalid values use the default', () => {
  assert.equal(reportGenerationLeaseMs({ REPORT_GENERATION_LEASE_MS: '30000' }), 30_000);
  assert.equal(reportGenerationLeaseMs({ REPORT_GENERATION_LEASE_MS: 'invalid' }), DEFAULT_REPORT_GENERATION_LEASE_MS);
  assert.equal(reportGenerationLeaseMs({ REPORT_GENERATION_LEASE_MS: '0' }), DEFAULT_REPORT_GENERATION_LEASE_MS);
});
