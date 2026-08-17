import assert from 'node:assert/strict'
import test from 'node:test'

import {
  compactNetworkLog,
  safeDebugValue,
  safePublicDebugValue,
} from '../src/lib/debugExport.js'

const get = (ts, url, value, duration = 10) => ({
  ts,
  method: 'GET',
  url,
  status: 200,
  duration_ms: duration,
  req_body: null,
  res_preview: value,
})

test('interleaved unchanged polling responses collapse inside one action phase', () => {
  const compacted = compactNetworkLog([
    get('t1', '/workspace', { revision: 1 }, 8),
    get('t2', '/proposals', { proposals: [] }, 12),
    get('t3', '/workspace', { revision: 1 }, 5),
    get('t4', '/proposals', { proposals: [] }, 20),
  ])

  assert.equal(compacted.length, 2)
  assert.equal(compacted[0].repeat_count, 2)
  assert.equal(compacted[0].last_ts, 't3')
  assert.equal(compacted[0].duration_ms_min, 5)
  assert.equal(compacted[1].repeat_count, 2)
  assert.equal(compacted[1].duration_ms_max, 20)
})

test('changed GET responses and identical responses after an action remain visible', () => {
  const compacted = compactNetworkLog([
    get('t1', '/workspace', { revision: 1 }),
    get('t2', '/workspace', { revision: 2 }),
    { ts: 't3', method: 'POST', url: '/chat', status: 200, duration_ms: 30 },
    get('t4', '/workspace', { revision: 2 }),
  ])

  assert.equal(compacted.length, 4)
  assert.equal(compacted[0].repeat_count, 1)
  assert.equal(compacted[1].res_preview.revision, 2)
  assert.equal(compacted[2].method, 'POST')
  assert.equal(compacted[3].repeat_count, 1)
})

test('backend log fetch is omitted because backend_logs already contains it', () => {
  const compacted = compactNetworkLog([
    get('t1', '/agent/api/agent/logs/session?limit=500', { omitted: true }),
    get('t2', '/workspace', { revision: 1 }),
  ])
  assert.deepEqual(compacted.map(entry => entry.url), ['/workspace'])
})

test('debug values still redact secrets and omit binary payloads', () => {
  const safe = safeDebugValue({
    authorization: 'Bearer secret',
    imageBase64: '123456',
    nested: { ok: true },
  })
  assert.equal(safe.authorization, '[redacted]')
  assert.match(safe.imageBase64, /omitted binary payload/)
  assert.equal(safe.nested.ok, true)
})

test('public debug exports omit engine metadata and scrub provider names', () => {
  const safe = safePublicDebugValue({
    conversation_model: 'openai_gpt_5_4_mini',
    nested: {
      provider: 'greennode',
      route_key: 'openai:gpt-5.4-mini',
      detail: 'OpenAI request replaced a GreenNode fallback',
      modeled_estimate: true,
    },
  })
  assert.equal('conversation_model' in safe, false)
  assert.equal('provider' in safe.nested, false)
  assert.equal('route_key' in safe.nested, false)
  assert.doesNotMatch(safe.nested.detail, /GreenNode|OpenAI|MiniMax|GPT/i)
  assert.equal(safe.nested.modeled_estimate, true)
})
