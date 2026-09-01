import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { transform } from 'esbuild'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const source = await readFile(new URL('../src/components/InvestigationEvidence.jsx', import.meta.url), 'utf8')
const { code } = await transform(source, { loader: 'jsx', jsx: 'automatic', format: 'cjs' })
const module = { exports: {} }
new Function('require', 'module', 'exports', code)(createRequire(import.meta.url), module, module.exports)
const { HypothesisEvidence, EvidenceObservation, investigationControl } = module.exports
const observation = { evidence_id: 'EVD-size', probe_id: 'creative_compatibility', source: 'derived', status: 'anomaly',
  observed_at: '2026-09-01T02:00:00Z', summary: 'Metadata mismatch', evidence: { actual: '600x180', expected: '1160x250' } }
const bundle = { probes: [observation], hypotheses: [{ hypothesis_id: 'creative_contract_mismatch', label: 'Creative không khớp placement',
  status: 'supported', claim_scope: 'creative_metadata', supporting_evidence_ids: ['EVD-size'], contradicting_evidence_ids: [],
  evidence_links: [{ evidence_id: 'EVD-size', relation: 'supports' }], explanation: 'Only metadata checked', limitations: ['Not CTR causality'], missing_evidence: [] },
  { hypothesis_id: 'configuration_drift', label: 'Cấu hình khác baseline', status: 'unknown',
    evidence_links: [{ evidence_id: 'EVD-size', relation: 'context' }], missing_evidence: ['Cần kiểm tra config'] }] }

test('renders actual hypothesis cards with separate direct/context evidence and no invented confidence', () => {
  const html = renderToStaticMarkup(React.createElement(HypothesisEvidence, { bundle }))
  for (const value of ['Có quan sát hỗ trợ', 'Chưa đủ bằng chứng', 'Cần kiểm tra tiếp', 'Metadata creative / catalog',
    '600x180', '1160x250', 'EVD-size', 'derived', '2026-09-01T02:00:00Z', 'Bối cảnh — không kết luận nguyên nhân']) assert.ok(html.includes(value), value)
  assert.doesNotMatch(html.replace(/<[^>]*>/g, ''), /0 điểm|score_share|[0-9]+%/)
  assert.match(html, /<details/)
  assert.match(html, /aria-label="Giả thuyết và bằng chứng"/)
})

test('conflict and missing evidence are visible and untrusted prose is escaped', () => {
  const copy = structuredClone(bundle)
  copy.hypotheses[0].status = 'conflicting'
  copy.hypotheses[0].label = '<script>unsafe()</script>'
  const html = renderToStaticMarkup(React.createElement(HypothesisEvidence, { bundle: copy }))
  assert.match(html, /Bằng chứng mâu thuẫn/)
  assert.match(html, /&lt;script&gt;/)
  assert.doesNotMatch(html, /<script>/)
  assert.match(renderToStaticMarkup(React.createElement(EvidenceObservation, {})), /Dẫn chứng không còn/)
})

const incident = { incident_id: 'INC-one', dataset_revision: 2 }
const job = { incident_id: 'INC-one', dataset_revision: 2, policy_version: 'p1', engine_version: 'multi-agent-v3', attempts: 1, model_calls: 8 }
test('running work cannot be submitted twice; partial work exposes resume, not fresh budget', () => {
  const control = updates => investigationControl(incident, [{ ...job, ...updates }], 'p1', 'multi-agent-v3')
  assert.deepEqual(control({ status: 'running' }), { label: 'L2 đang chạy nền', disabled: true })
  assert.deepEqual(control({ status: 'partial' }), { label: 'Tiếp tục điều tra', disabled: false })
  assert.equal(control({ status: 'failed', model_calls: 24 }).disabled, true)
  assert.equal(control({ status: 'partial', attempts: 3 }).disabled, true)
  assert.equal(control({ status: 'completed' }).disabled, true)
})

test('old dataset, policy, engine, or different incident does not disable a new investigation', () => {
  for (const stale of [{ dataset_revision: 1 }, { policy_version: 'old' }, { engine_version: 'multi-agent-v2' }, { incident_id: 'INC-other' }]) {
    assert.deepEqual(investigationControl(incident, [{ ...job, status: 'completed', ...stale }], 'p1', 'multi-agent-v3'),
      { label: 'Điều tra L2', disabled: false })
  }
})
