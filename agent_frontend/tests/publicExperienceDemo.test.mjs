import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { authReturnTo, hasAgentIntent } from '../src/lib/publicExperience.js'
import { AUTOPILOT_TOUR_STEPS } from '../src/demo/autopilotTour.js'
import { getDemoDateRange, pickRandomBrief } from '../src/demo/demoScripts.js'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const landing = read('../src/components/PublicLanding.jsx')
const engine = read('../src/demo/DemoEngine.jsx')
const scripts = read('../src/demo/demoScripts.js')
const app = read('../src/App.jsx')
const home = read('../src/components/ExperienceSelector.jsx')
const autopilot = read('../src/components/AutopilotPanel.jsx')
const imageGenerator = read('../src/steps/creative/AdImageGenerator.jsx')
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
  assert.match(landing, /campaign-agent-core/)
  assert.match(landing, /\/brand\/advertising-agent-mascot\.png/)
  assert.match(landing, /landing-nav-signal/)
  assert.equal(existsSync(new URL('../public/brand/advertising-agent-mascot.png', import.meta.url)), true)
  assert.match(landing, /SignalRibbon/)
  assert.match(landing, /\[0, 1, 2\]\.map/)
  assert.match(landing, /CampaignTruthVisual/)
  assert.match(landing, /landing-manifesto-chapter/)
  assert.match(landing, /IntersectionObserver/)
  assert.match(landing, /data-scroll-reveal/)
  assert.match(landing, /Chọn Copilot để cùng Agent xây từng quyết định/)
  assert.doesNotMatch(landing, /Không phải hai giao diện đổi màu/)
  assert.match(landing, /mode-visual-copilot/)
  assert.match(landing, /mode-visual-autopilot/)
  assert.match(landing, /<em>chuyển động\.<\/em>/)
  assert.doesNotMatch(landing, /310 segments/)
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
  assert.match(app, /onPrepareLive=\{handleReset\}/)
  assert.match(engine, /await onPrepareLive\?\.\(\)/)
  assert.doesNotMatch(app, /demo:new_chat/)
  assert.doesNotMatch(engine, /demo:new_chat/)
  assert.match(app, /window\.scrollTo\(\{ top: 0, left: 0, behavior: 'auto' \}\)/)
  assert.match(app, /appShellRef\.current\?\.scrollTo\(\{ top: 0, left: 0, behavior: 'auto' \}\)/)
  assert.match(app, /ref=\{appShellRef\} className="fixed inset-0 flex h-screen flex-col overflow-clip/)
})

test('Copilot creative walkthrough teaches assets, prompt composition, and quota consent', () => {
  for (const target of [
    'creative-reference-assets',
    'image-quota-counter',
    'image-quota-consent',
  ]) {
    assert.match(imageGenerator, new RegExp(`data-demo="${target}"`))
    assert.match(scripts, new RegExp(`data-demo="${target}"`))
  }
  assert.match(imageGenerator, /id="image-quota-checkbox"/)
  assert.match(scripts, /target: '#btn-compose-creative-prompt'/)
  assert.match(scripts, /target: '\[data-testid="creative-prompt-spec"\]'/)
  assert.match(scripts, /target: '#image-quota-checkbox'/)

  const consentIndex = scripts.indexOf("target: '#image-quota-checkbox'")
  const generateIndex = scripts.indexOf("target: '#btn-ai-generate'", consentIndex)
  assert.ok(consentIndex >= 0)
  assert.ok(generateIndex > consentIndex)
})

test('every live walkthrough uses yesterday through seven days later', () => {
  const now = new Date(2026, 6, 20, 12, 0, 0)
  assert.deepEqual(getDemoDateRange(now), {
    startDate: '2026-07-19',
    endDate: '2026-07-26',
    displayStart: '19/07/2026',
    displayEnd: '26/07/2026',
  })

  const brief = pickRandomBrief(now)
  assert.equal(brief.briefPatch.startDate, '2026-07-19')
  assert.equal(brief.briefPatch.endDate, '2026-07-26')
  assert.match(brief.chatMessage, /Thời gian: 19\/07\/2026 đến 26\/07\/2026/)
  assert.doesNotMatch(scripts, /2026-06-30|2026-07-07|30\/6\/2026|7\/7\/2026/)
})

test('Autopilot guided tour maps every entry decision to the actual canvas', () => {
  assert.deepEqual(AUTOPILOT_TOUR_STEPS.map(step => step.target), [
    '[data-demo="autopilot-canvas"]',
    '[data-demo="autopilot-intro"]',
    '[data-demo="autopilot-guide"]',
    '[data-demo="autopilot-brief-status"]',
    '[data-demo="autopilot-creative-source"]',
    '[data-demo="autopilot-policy"]',
    '[data-demo="chat-pane"]',
    '[data-demo="autopilot-start"]',
  ])
  for (const target of ['autopilot-canvas', 'autopilot-intro', 'autopilot-guide', 'autopilot-creative-source', 'autopilot-policy', 'autopilot-brief-status', 'autopilot-start']) {
    assert.match(autopilot, new RegExp(`data-demo="${target}"`))
  }
  assert.match(autopilot, /KPI \+ ghi chú audience\/thị trường/)
  assert.match(autopilot, /Upload khi đã có asset chính thức/)
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
  assert.match(styles, /translate3d\(-33\.333333%/)
  assert.match(styles, /signal-ribbon-track \{[^}]*top:34px[^}]*rotate\(-\.35deg\)/)
  assert.match(styles, /\.scroll-reveal\.is-visible/)
})
