import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { scenarioFrameUrl, isScenarioEvent } from '../scenario-lab.js'

test('campaign URL is encoded and fixed to the Agent controller route', () => {
  const url = scenarioFrameUrl('https://agent.example/', 'ORD/x?evil=1')
  assert.equal(url.pathname, '/evaluation/scenarios')
  assert.equal(url.searchParams.get('campaignId'), 'ORD/x?evil=1')
})
test('only the configured frame, origin and campaign can refresh charts', () => {
  const sender = {}, frame = { contentWindow: sender }
  const event = { source: sender, origin: 'https://agent.example', data: { type: 'scenario-applied', campaignId: 'ORD-1' } }
  assert.equal(isScenarioEvent(event, frame, event.origin, 'ORD-1'), true)
  assert.equal(isScenarioEvent({ ...event, source: {} }, frame, event.origin, 'ORD-1'), false)
  assert.equal(isScenarioEvent({ ...event, origin: 'https://evil.example' }, frame, event.origin, 'ORD-1'), false)
  assert.equal(isScenarioEvent(event, frame, event.origin, 'ORD-2'), false)
})

test('mobile filters cannot expand the page behind Scenario Lab', async () => {
  const css = await readFile(new URL('../style.css', import.meta.url), 'utf8')
  assert.match(css, /@media \(max-width: 900px\)[\s\S]*\.filter-group \{ width: 100%; min-width: 0; \}/)
  assert.match(css, /\.filterbar select,[\s\S]*min-width: 0; max-width: 100%;/)
})
