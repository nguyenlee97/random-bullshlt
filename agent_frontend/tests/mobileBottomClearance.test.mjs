import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const topBar = fs.readFileSync(new URL('../src/components/TopBar.jsx', import.meta.url), 'utf8')
const app = fs.readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const css = fs.readFileSync(new URL('../src/index.css', import.meta.url), 'utf8')

test('mobile header offers persisted manual bottom-clearance choices', () => {
  assert.match(topBar, /advertising-agent:mobile-bottom-clearance/)
  assert.match(topBar, /Nâng đáy giao diện/)
  assert.match(topBar, /value: 0/)
  assert.match(topBar, /value: 24/)
  assert.match(topBar, /value: 48/)
  assert.match(topBar, /value: 72/)
  assert.match(topBar, /window\.localStorage\.setItem/)
  assert.match(topBar, /--mobile-bottom-clearance/)
  assert.match(topBar, /mobile-bottom-clearance-btn/)
})

test('manual clearance applies to the complete mobile shell without changing fine-pointer desktop padding', () => {
  assert.match(app, /className="mobile-app-shell/)
  assert.match(css, /padding-bottom:\s*calc\(env\(safe-area-inset-bottom,\s*0px\)\s*\+\s*var\(--mobile-bottom-clearance,\s*0px\)\)/)
  assert.match(css, /@media \(max-width:\s*767px\),\s*\(pointer:\s*coarse\)/)
  assert.match(css, /@media \(min-width:\s*768px\) and \(pointer:\s*fine\)/)
  assert.match(css, /\.mobile-app-shell\s*\{[\s\S]*?height:\s*100vh;[\s\S]*?padding-bottom:\s*0;/)
})
