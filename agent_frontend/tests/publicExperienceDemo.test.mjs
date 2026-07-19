import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { authReturnTo, hasAgentIntent } from '../src/lib/publicExperience.js'
import { AUTOPILOT_TOUR_STEPS } from '../src/demo/autopilotTour.js'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const landing = read('../src/components/PublicLanding.jsx')
const engine = read('../src/demo/DemoEngine.jsx')
const scripts = read('../src/demo/demoScripts.js')
const app = read('../src/App.jsx')
const home = read('../src/components/ExperienceSelector.jsx')
const autopilot = read('../src/components/AutopilotPanel.jsx')
const docs = read('../public/tech-docs.html')
const styles = read('../src/index.css')

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

test('landing uses a kinetic campaign system and opens real guided tours', () => {
  assert.match(landing, /CampaignConstellation/)
  assert.match(landing, /campaign-stage/)
  assert.match(landing, /onOpenDemo\('copilot'\)/)
  assert.match(landing, /onOpenDemo\(mode\)/)
  assert.match(landing, /\/tech-docs\.html/)
  assert.match(app, /enterAgentForDemo/)
  assert.match(app, /startGuidedDemo/)
  assert.doesNotMatch(app, /ProductDemo/)
})

test('agent homepage exposes unmistakable workspace CTAs and ordered guided tours', () => {
  assert.match(home, /Mở .*workspace/)
  assert.match(home, /min-h-14/)
  assert.match(home, /Guided tour/)
  assert.match(home, /Workspace entrance/)
  assert.match(home, /Bắt đầu ẩn danh — không cần đăng nhập/)
})

test('Copilot demo is restored as a spotlight tour over the real interface', () => {
  assert.match(engine, /DemoOverlay/)
  assert.match(engine, /STAGE1_STEPS/)
  assert.match(engine, /buildStage2Steps/)
  assert.match(engine, /data-demo="chat-pane"/)
  assert.match(scripts, /Brief → Audience → Creative → Setup → Launch review/)
  assert.doesNotMatch(scripts, /type: 'CLICK_EL', target: '#create-campaign-btn'/)
})

test('Autopilot guided tour maps every entry decision to the actual canvas', () => {
  assert.deepEqual(AUTOPILOT_TOUR_STEPS.map(step => step.target), [
    '[data-demo="autopilot-canvas"]',
    '[data-demo="autopilot-intro"]',
    '[data-demo="autopilot-creative-source"]',
    '[data-demo="autopilot-policy"]',
    '[data-demo="autopilot-brief-status"]',
    '[data-demo="chat-pane"]',
    '[data-demo="autopilot-start"]',
  ])
  for (const target of ['autopilot-canvas', 'autopilot-intro', 'autopilot-creative-source', 'autopilot-policy', 'autopilot-brief-status', 'autopilot-start']) {
    assert.match(autopilot, new RegExp(`data-demo="${target}"`))
  }
})

test('technical document removes part 10 and forces a reliable Agent navigation', () => {
  assert.doesNotMatch(docs, /id="evidence"/)
  assert.doesNotMatch(docs, /<span class="n">10<\/span>/)
  assert.match(docs, /href="\/agent\?from=docs" id="agent-entry-link"/)
  assert.doesNotMatch(docs, /agent-entry-link.*preventDefault|window\.location\.assign/)
})

test('public experience is responsive and honors reduced motion', () => {
  assert.match(styles, /@media \(max-width: 700px\)/)
  assert.match(styles, /prefers-reduced-motion: reduce/)
  assert.match(styles, /campaign-stage \*/)
  assert.match(styles, /animation: none !important/)
})
