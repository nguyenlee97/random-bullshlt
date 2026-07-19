import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const confirm = readFileSync(new URL('../src/steps/setup/ConfirmPhase.jsx', import.meta.url), 'utf8')

test('order creation uses the shared response adapter so guard details survive', () => {
  const start = api.indexOf('export async function createCampaignOrder')
  const end = api.indexOf('function safeDemoFallback', start)
  const implementation = api.slice(start, end)

  assert.match(implementation, /await callAgent\(/)
  assert.match(implementation, /response\?\.metadata\?\.tool/)
  assert.doesNotMatch(implementation, /await agentFetch\(/)
})

test('guard rejection refreshes live conflicts and offers zone recovery', () => {
  assert.match(confirm, /response\?\.metadata\?\.tool === 'order_guard'/)
  assert.match(confirm, /await fetchZonesFromAgent\(\)/)
  assert.match(confirm, /response\?\.content/)
  assert.match(confirm, /Chọn zone khác/)
})

test('setup confirmation does not render unknown audience size as zero people', () => {
  assert.match(confirm, /hasKnownAudienceSize/)
  assert.match(confirm, /hasAudienceEstimate \? `\$\{fmt\(segment\?\.size \|\| 0\)\} người` : '—'/)
  assert.match(confirm, /Catalog chưa cung cấp size/)
})
