import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'


test('Guided proactive entry effects never run inside Autopilot', () => {
  const source = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
  const audienceEffect = source.slice(
    source.indexOf('// Audience-entry:'),
    source.indexOf('// Setup-entry:'),
  )
  const setupEffect = source.slice(
    source.indexOf('// Setup-entry:'),
    source.indexOf('// Report-entry:'),
  )

  assert.match(audienceEffect, /experienceMode === 'guided'/)
  assert.match(setupEffect, /experienceMode === 'guided'/)
})
