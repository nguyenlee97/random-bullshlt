import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { authReturnTo, hasAgentIntent } from '../src/lib/publicExperience.js'
import { createDemoState, DEMO_JOURNEYS, demoTransition, REPORT_VIEWS } from '../src/demo/demoJourneys.js'

const landing = readFileSync(new URL('../src/components/PublicLanding.jsx', import.meta.url), 'utf8')
const demo = readFileSync(new URL('../src/components/ProductDemo.jsx', import.meta.url), 'utf8')
const engine = readFileSync(new URL('../src/demo/DemoEngine.jsx', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const home = readFileSync(new URL('../src/components/ExperienceSelector.jsx', import.meta.url), 'utf8')
const styles = readFileSync(new URL('../src/index.css', import.meta.url), 'utf8')

test('public landing routes ordinary visitors to /agent while callbacks and deep links bypass it', () => {
  assert.equal(hasAgentIntent({ pathname: '/', search: '' }), false)
  assert.equal(hasAgentIntent({ pathname: '/agent', search: '' }), true)
  assert.equal(hasAgentIntent({ pathname: '/', search: '?conversation=conv_123' }), true)
  assert.equal(hasAgentIntent({ pathname: '/', search: '?auth=success' }), true)
  assert.match(app, /<PublicLanding/)
  assert.match(app, /agentEntryUrl\(window\.location\)/)
  assert.match(app, /pendingConversationDeepLinkRef/)
})

test('Zalo callback return path retains conversation and hash while removing callback residue', () => {
  assert.equal(
    authReturnTo({ pathname: '/agent', search: '?conversation=abc&auth=ok&theme=dark', hash: '#workspace' }),
    '/agent?conversation=abc&theme=dark#workspace',
  )
})

test('landing exposes Agent, both demos and technical documentation', () => {
  assert.match(landing, /Bắt đầu với Agent/)
  assert.match(landing, /Xem Copilot demo/)
  assert.match(landing, /Xem Autopilot demo/)
  assert.match(landing, /\/tech-docs\.html/)
  assert.match(landing, /Dùng ẩn danh ngay/)
})

test('agent onboarding copy distinguishes anonymous and synchronized account states', () => {
  assert.match(home, /Bắt đầu ẩn danh — không cần đăng nhập/)
  assert.match(home, /Đăng nhập Zalo \(tuỳ chọn\)/)
  assert.match(home, /Lịch sử đa thiết bị/)
  assert.match(home, /liên kết Zalo OA/)
  assert.match(home, /email\/password|email dành cho kiểm thử|Đăng nhập Zalo/)
})

test('Copilot demo follows every review-aware stage without campaign side effects', () => {
  const ids = DEMO_JOURNEYS.copilot.steps.map(step => step.id)
  assert.deepEqual(ids, [
    'copilot-request', 'copilot-brief', 'copilot-audience', 'copilot-creative-review',
    'copilot-setup', 'copilot-launch', 'copilot-result', 'copilot-reports',
  ])
  assert.match(DEMO_JOURNEYS.copilot.steps[3].eyebrow, /Review bắt buộc/)
  assert.match(DEMO_JOURNEYS.copilot.steps[5].description, /không gọi endpoint tạo order/)
})

test('Autopilot demo follows its durable state machine and includes all six reports', () => {
  const ids = DEMO_JOURNEYS.autopilot.steps.map(step => step.id)
  for (const id of ['autopilot-policy', 'autopilot-strategy', 'autopilot-audience', 'autopilot-creative', 'autopilot-placement', 'autopilot-review', 'autopilot-launch', 'autopilot-timeline', 'autopilot-reports', 'autopilot-zalo']) {
    assert.ok(ids.includes(id), `${id} is missing`)
  }
  assert.equal(REPORT_VIEWS.length, 6)
  assert.deepEqual(DEMO_JOURNEYS.autopilot.steps.find(step => step.id === 'autopilot-reports').reports, REPORT_VIEWS)
})

test('demo reducer supports pause, skip, restart and bounded transitions', () => {
  let state = createDemoState('copilot')
  state = demoTransition(state, { type: 'TOGGLE_PAUSE' })
  assert.equal(state.paused, true)
  state = demoTransition(state, { type: 'SKIP' })
  assert.equal(state.completed, true)
  assert.equal(state.index, DEMO_JOURNEYS.copilot.steps.length - 1)
  state = demoTransition(state, { type: 'RESTART' })
  assert.deepEqual(state, createDemoState('copilot'))
  state = demoTransition(state, { type: 'PREVIOUS' })
  assert.equal(state.index, 0)
})

test('all demo surfaces remain deterministic and never invoke campaign APIs', () => {
  assert.match(demo, /data-demo-sandbox="true"/)
  assert.match(engine, /deterministic sandbox/)
  assert.doesNotMatch(`${demo}\n${engine}`, /AgentAPI|createCampaign|create-campaign-btn|onSendMessage\(|onApprove\(|fetch\(/)
})

test('public experience is responsive and honors reduced motion', () => {
  assert.match(landing, /sm:text-7xl/)
  assert.match(demo, /sm:grid-cols-\[150px_1fr\]/)
  assert.match(styles, /prefers-reduced-motion: reduce/)
  assert.match(styles, /animation: none !important/)
})
