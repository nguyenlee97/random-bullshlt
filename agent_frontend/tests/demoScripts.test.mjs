import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { buildStage2Steps } from '../src/demo/demoScripts.js'

const creativeStep = readFileSync(
  new URL('../src/steps/CreativeStep.jsx', import.meta.url),
  'utf8',
)
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')

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
    '[data-demo="creative-file-card"][data-ai-generated="true"][data-format-id="zuma-box"]',
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
    '[data-demo="creative-file-card"][data-ai-generated="true"][data-format-id="zuma-box"]',
  ))
})

test('generated creative identity is exposed and consumed through stable metadata', () => {
  assert.match(creativeStep, /data-ai-generated=\{file\.aiGenerated \? 'true' : 'false'\}/)
  assert.match(creativeStep, /data-format-id=\{file\.formatId \|\| ''\}/)
  assert.match(app, /f\.aiGenerated && f\.formatId === 'zuma-box'/)
})
