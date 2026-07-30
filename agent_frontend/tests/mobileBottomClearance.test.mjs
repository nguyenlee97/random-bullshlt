import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const topBar = fs.readFileSync(new URL('../src/components/TopBar.jsx', import.meta.url), 'utf8')
const app = fs.readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const css = fs.readFileSync(new URL('../src/index.css', import.meta.url), 'utf8')

test('mobile header offers persisted manual bottom-clearance choices', () => {
  assert.match(topBar, /advertising-agent:mobile-bottom-clearance/)
  assert.match(topBar, /advertising-agent:mobile-bottom-help-seen/)
  assert.match(topBar, /Nâng đáy giao diện/)
  assert.match(topBar, /value: 0/)
  assert.match(topBar, /value: 24/)
  assert.match(topBar, /value: 48/)
  assert.match(topBar, /value: 72/)
  assert.match(topBar, /window\.localStorage\.setItem/)
  assert.match(topBar, /--mobile-bottom-clearance/)
  assert.match(topBar, /mobile-bottom-clearance-btn/)
  assert.match(topBar, /mobile-bottom-attention-button/)
  assert.match(topBar, /max-h-\[calc\(var\(--visual-viewport-height,100dvh\)-4\.5rem\)\]/)
  assert.match(topBar, /Nếu ô Chat hoặc nút gửi bị che/)
  assert.match(css, /@keyframes mobile-bottom-attention-flash/)
  assert.match(css, /prefers-reduced-motion:\s*reduce/)
})

test('workspace reset requires explicit confirmation and keeps current history recoverable', () => {
  assert.match(topBar, /setResetConfirmOpen\(true\)/)
  assert.match(topBar, /role="alertdialog"/)
  assert.match(topBar, /Đặt lại workspace\?/)
  assert.match(topBar, /Campaign và lịch sử hiện tại vẫn được lưu/)
  assert.match(topBar, /onReset\?\.\(\)/)
})

test('manual clearance applies to the complete mobile shell without changing fine-pointer desktop padding', () => {
  assert.match(app, /className="mobile-app-shell/)
  assert.match(css, /padding-bottom:\s*calc\(env\(safe-area-inset-bottom,\s*0px\)\s*\+\s*var\(--mobile-bottom-clearance,\s*0px\)\)/)
  assert.match(css, /@media \(max-width:\s*767px\),\s*\(pointer:\s*coarse\)/)
  assert.match(css, /@media \(min-width:\s*768px\) and \(pointer:\s*fine\)/)
  assert.match(css, /\.mobile-app-shell\s*\{[\s\S]*?height:\s*100vh;[\s\S]*?padding-bottom:\s*0;/)
})
