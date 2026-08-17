import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { waitForDemoElement } from '../src/demo/demoElementWait.js'

const engine = readFileSync(new URL('../src/demo/DemoEngine.jsx', import.meta.url), 'utf8')
const walkthrough = readFileSync(new URL('../src/demo/autopilotWalkthrough.js', import.meta.url), 'utf8')
const workspacePane = readFileSync(new URL('../src/components/WorkspacePane/index.jsx', import.meta.url), 'utf8')

test('walkthrough waits for a temporarily missing element', async () => {
  const expected = { id: 'assignment-editor' }
  let attempts = 0
  const found = await waitForDemoElement('[data-demo="assignment-editor"]', {
    timeout: 100,
    interval: 0,
    querySelector: () => {
      attempts += 1
      return attempts >= 3 ? expected : null
    },
  })

  assert.equal(found, expected)
  assert.equal(attempts, 3)
})

test('walkthrough element wait returns null instead of pretending success', async () => {
  const found = await waitForDemoElement('[data-demo="missing"]', {
    timeout: 1,
    interval: 0,
    querySelector: () => null,
  })

  assert.equal(found, null)
})

test('walkthrough click and selector steps fail closed and retry the same step', () => {
  assert.match(engine, /const el = await waitForDemoElement\(step\.target/)
  assert.match(engine, /CLICK_EL target not found:[\s\S]*retry_current_step[\s\S]*return/)
  assert.match(engine, /WAIT_FOR_SELECTOR timeout[\s\S]*retry_current_step[\s\S]*return/)
})

test('assignment walkthrough only saves the assignment editor', () => {
  assert.match(workspacePane, /data-autopilot-editor-artifact=\{autopilotEditorArtifact \|\| ''\}/)
  assert.match(
    walkthrough,
    /data-autopilot-editor-artifact="assignments"\]:not\(:disabled\)/,
  )
  assert.match(
    walkthrough,
    /data-autopilot-editor-artifact="creative"/,
  )
})
