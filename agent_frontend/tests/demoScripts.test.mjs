import assert from 'node:assert/strict'
import test from 'node:test'

import { buildStage2Steps } from '../src/demo/demoScripts.js'

const brief = {
  id: 'test',
  brand: 'Test',
  chatMessage: 'Test brief',
  briefPatch: {},
  budgetEdit: 100,
}

test('OpenAI walkthrough waits for the auto-persisted creative', () => {
  const steps = buildStage2Steps(brief, { openaiCampaignFlow: true })
  const targets = steps.map(step => step.target).filter(Boolean)

  assert.ok(targets.includes(
    '[data-demo="creative-file-card"][data-file-id^="ai-zuma-box"]',
  ))
  assert.ok(!targets.includes('[id^="gen-img-ai-zuma-box"]'))
  assert.ok(!targets.includes('#btn-add-to-creative'))
})

test('GreenNode walkthrough retains manual gallery selection', () => {
  const steps = buildStage2Steps(brief)
  const targets = steps.map(step => step.target).filter(Boolean)

  assert.ok(targets.includes('[id^="gen-img-ai-zuma-box"]'))
  assert.ok(targets.includes('#btn-add-to-creative'))
  assert.ok(!targets.includes(
    '[data-demo="creative-file-card"][data-file-id^="ai-zuma-box"]',
  ))
})
