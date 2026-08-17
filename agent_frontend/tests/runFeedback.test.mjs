import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const component = fs.readFileSync(
  new URL('../src/components/feedback/RunFeedback.jsx', import.meta.url),
  'utf8',
)
const api = fs.readFileSync(
  new URL('../src/api/agentApi.js', import.meta.url),
  'utf8',
)
const guided = fs.readFileSync(
  new URL('../src/components/WorkspacePane/index.jsx', import.meta.url),
  'utf8',
)
const autopilot = fs.readFileSync(
  new URL('../src/components/AutopilotOutcome.jsx', import.meta.url),
  'utf8',
)

test('feedback is additive and targets completed run surfaces', () => {
  assert.match(component, /data-testid="run-feedback"/)
  assert.match(component, /wrong_recommendation/)
  assert.match(component, /AgentAPI\.submitFeedback/)
  assert.match(component, /VITE_RUN_FEEDBACK_ENABLED/)
  assert.match(guided, /surface: 'guided_result'/)
  assert.match(autopilot, /surface: 'autopilot_summary'/)
  assert.match(autopilot, /targetKind: 'run'/)
})

test('feedback API uses the owned session and existing CSRF-aware transport', () => {
  assert.match(api, /async submitFeedback\(payload\)/)
  assert.match(api, /session_id: payload\.session_id \|\| SESSION_ID/)
  assert.match(api, /agentFetch\(`\$\{AGENT_URL\}\/api\/agent\/feedback`/)
  assert.doesNotMatch(component, /workspace_update|approve|create_order/)
})
