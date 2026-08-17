import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const panel = readFileSync(
  new URL('../src/components/AutopilotPanel.jsx', import.meta.url),
  'utf8',
)
const app = readFileSync(
  new URL('../src/App.jsx', import.meta.url),
  'utf8',
)
const api = readFileSync(
  new URL('../src/api/agentApi.js', import.meta.url),
  'utf8',
)

test('approval policy stays locked until a creative approach is selected', () => {
  assert.match(panel, /const policyLocked = !creativeSource/)
  assert.match(panel, /const policyDisabled = policyLocked \|\| uploadBlocksAutomatic \|\| loading/)
  assert.match(panel, /disabled=\{policyDisabled\}/)
  assert.match(panel, /autopilot-policy-locked/)
})

test('chat guides the user through creative source and then approval policy', () => {
  assert.match(app, /Brief đã được xác nhận/)
  assert.match(app, /chọn \*\*cách chuẩn bị creative\*\*/)
  assert.match(panel, /autopilot_creative_source_selected/)
  assert.match(panel, /chọn \*\*cách Agent xin duyệt\*\*/)
})

test('each preference click uses a fresh mutation id so A to B to A is applied', () => {
  assert.match(api, /const preferenceMutationId =/)
  assert.match(api, /globalThis\.crypto\?\.randomUUID\?\.\(\)/)
  assert.match(api, /idempotency_key: `experience:\$\{SESSION_ID\}:\$\{preferenceMutationId\}`/)
  assert.doesNotMatch(
    api,
    /idempotency_key: `experience:\$\{SESSION_ID\}:\$\{experienceMode\}:\$\{approvalPolicy/,
  )
})
