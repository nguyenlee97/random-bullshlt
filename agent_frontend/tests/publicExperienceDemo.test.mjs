import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { authReturnTo, hasAgentIntent } from '../src/lib/publicExperience.js'
import { AUTOPILOT_TOUR_STEPS } from '../src/demo/autopilotTour.js'
import { buildAutopilotLiveSteps } from '../src/demo/autopilotWalkthrough.js'
import { getDemoDateRange, pickRandomBrief } from '../src/demo/demoScripts.js'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const landing = read('../src/components/PublicLanding.jsx')
const engine = read('../src/demo/DemoEngine.jsx')
const scripts = read('../src/demo/demoScripts.js')
const app = read('../src/App.jsx')
const home = read('../src/components/ExperienceSelector.jsx')
const overlay = read('../src/demo/DemoOverlay.jsx')
const autopilot = read('../src/components/AutopilotPanel.jsx')
const autopilotReview = read('../src/components/AutopilotReview.jsx')
const audienceStep = read('../src/steps/AudienceStep.jsx')
const targetingPanel = read('../src/components/TargetingPanel.jsx')
const workspacePane = read('../src/components/WorkspacePane/index.jsx')
const assignmentEditor = read('../src/steps/setup/CreativeAssignPhase.jsx')
const imageGenerator = read('../src/steps/creative/AdImageGenerator.jsx')
const creativeStep = read('../src/steps/CreativeStep.jsx')
const cropModal = read('../src/steps/creative/ImageCropModal.jsx')
const topBar = read('../src/components/TopBar.jsx')
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

test('Copilot creative walkthrough teaches assets and prompt composition without exposing provider or quota details', () => {
  assert.match(imageGenerator, /data-demo="creative-reference-assets"/)
  assert.match(scripts, /data-demo="creative-reference-assets"/)
  assert.match(scripts, /target: '#btn-compose-creative-prompt'/)
  assert.match(scripts, /target: '\[data-testid="creative-prompt-spec"\]'/)
  assert.doesNotMatch(imageGenerator, /image-quota-counter|image-quota-consent|image-quota-checkbox|GPT Image|OpenAI Creative/)
  assert.doesNotMatch(scripts, /image-quota-counter|image-quota-consent|image-quota-checkbox|GPT Image|quota/)
  assert.match(imageGenerator, /disabled=\{!selectedFormatId \|\| generating\}/)
})

test('Copilot creative walkthrough waits for analysis and handles manual review before Setup', () => {
  for (const marker of [
    'data-demo="creative-review-state"',
    'data-review-terminal=',
    'data-demo="creative-manual-review"',
    'id="creative-manual-review-reason"',
    'id="creative-manual-review-approve"',
  ]) {
    assert.match(creativeStep, new RegExp(marker))
  }

  assert.match(engine, /case 'WAIT_FOR_CREATIVE_REVIEW'/)
  assert.match(engine, /step\.whenReviewState/)
  assert.match(engine, /currentCreativeReviewState/)
  assert.match(engine, /isCreativeReviewTerminal\(\) && reviewStates\.includes\(state\)/)
  assert.match(scripts, /whenReviewState: 'blocked'/)
  assert.match(engine, /if \(step\.autoAdvance && inputEl\)/)

  const analyzeIndex = scripts.indexOf("title: '🔎 Phân tích Creative Intelligence'")
  const terminalWaitIndex = scripts.indexOf("type: 'WAIT_FOR_CREATIVE_REVIEW'", analyzeIndex)
  const manualReasonIndex = scripts.indexOf("target: '#creative-manual-review-reason'", terminalWaitIndex)
  const manualAutoAdvanceIndex = scripts.indexOf('autoAdvance: true', manualReasonIndex)
  const readyWaitIndex = scripts.indexOf("reviewStates: ['ready']", manualReasonIndex)
  const confirmIndex = scripts.indexOf("title: '✅ Phân tích hoàn tất — tiếp tục sang Setup'", readyWaitIndex)
  const setupIndex = scripts.indexOf("metaTool: 'setup_entry'", confirmIndex)

  assert.ok(analyzeIndex >= 0)
  assert.ok(terminalWaitIndex > analyzeIndex)
  assert.ok(manualReasonIndex > terminalWaitIndex)
  assert.ok(manualAutoAdvanceIndex > manualReasonIndex)
  assert.ok(manualAutoAdvanceIndex < readyWaitIndex)
  assert.ok(readyWaitIndex > manualReasonIndex)
  assert.ok(confirmIndex > readyWaitIndex)
  assert.ok(setupIndex > confirmIndex)
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

test('Autopilot walkthrough explains internals, edits real review artifacts, and stops before launch', () => {
  const brief = pickRandomBrief(new Date(2026, 6, 23, 12, 0, 0))
  const live = buildAutopilotLiveSteps(brief, { creativeSource: 'ai_generate' })
  const types = live.map(step => step.type)

  assert.ok(types.includes('APPLY_AUTOPILOT_BRIEF'))
  assert.ok(types.includes('WAIT_FOR_AUTOPILOT_TASK'))
  assert.ok(types.includes('TRIM_AUTOPILOT_AUDIENCE'))
  assert.ok(types.includes('CHANGE_AUTOPILOT_TARGETING'))
  assert.ok(types.includes('TRIM_AUTOPILOT_PLACEMENTS'))
  assert.match(JSON.stringify(live), /Duyệt từng giai đoạn/)
  assert.match(JSON.stringify(live), /human-in-the-loop/)
  assert.match(JSON.stringify(live), /Tự xây dựng bản nháp/)
  assert.match(JSON.stringify(live), /autopilot-plan-details/)
  assert.match(JSON.stringify(live), /autopilot-strategy-calculation/)
  assert.match(JSON.stringify(live), /autopilot-technical-details/)
  assert.doesNotMatch(JSON.stringify(live), /OpenAI|GPT Image|quota|VLM/)

  const waits = live
    .filter(step => step.type === 'WAIT_FOR_AUTOPILOT_TASK')
    .flatMap(step => step.taskKeys)
  for (const checkpoint of [
    'retrieve_audience',
    'derive_targeting',
    'plan_placement_intent',
    'assign_creatives',
    'launch_approval',
  ]) {
    assert.ok(waits.includes(checkpoint), `missing ${checkpoint} checkpoint`)
  }

  assert.match(engine, /isOpenAIWalkthroughModel\(conversationModelRef\.current\)/)
  assert.match(engine, /buildAutopilotLiveSteps/)
  assert.match(engine, /whenAutopilotTask/)
  assert.match(engine, /case 'WAIT_FOR_AUTOPILOT_TASK'/)
  assert.match(engine, /case 'TRIM_AUTOPILOT_AUDIENCE'/)
  assert.match(engine, /case 'CHANGE_AUTOPILOT_TARGETING'/)
  assert.match(engine, /case 'TRIM_AUTOPILOT_PLACEMENTS'/)

  assert.match(audienceStep, /data-demo="autopilot-audience-option"/)
  assert.match(targetingPanel, /data-demo="autopilot-targeting-option"/)
  assert.match(autopilotReview, /data-demo="autopilot-placement-option"/)
  assert.match(workspacePane, /data-demo="autopilot-editor-save"/)
  assert.match(assignmentEditor, /data-demo="autopilot-creative-assignment-editor"/)
  assert.match(autopilot, /data-demo="autopilot-review-approve"/)
  assert.match(autopilot, /data-demo="autopilot-plan-details"/)
  assert.match(autopilot, /data-demo="autopilot-technical-details"/)

  const launchWait = live.findIndex(
    step => step.type === 'WAIT_FOR_AUTOPILOT_TASK' && step.taskKeys.includes('launch_approval'),
  )
  assert.ok(launchWait >= 0)
  assert.equal(
    live.slice(launchWait).some(
      step => step.type === 'CLICK_EL'
        && step.target?.includes('autopilot-review-approve')
        && step.target?.includes('launch_approval'),
    ),
    false,
  )
})

test('Autopilot walkthrough can use every pre-generated scenario creative without image generation', () => {
  const brief = pickRandomBrief(new Date(2026, 6, 23, 12, 0, 0))
  const live = buildAutopilotLiveSteps(brief, { creativeSource: 'upload' })
  const uploadChoice = live.find(step => step.target === '[data-demo="autopilot-source-upload"]')
  const injections = live.filter(step => step.type === 'INJECT_DEMO_CREATIVES')
  const uploadedCheckpoint = live.find(
    step => step.type === 'WAIT_FOR_AUTOPILOT_TASK' && step.taskKeys.includes('prepare_creatives'),
  )

  assert.ok(uploadChoice)
  assert.equal(injections.length, 2)
  assert.ok(injections.every(step => step.briefId === brief.id))
  assert.ok(injections.every(step => step.title && step.text))
  assert.ok(uploadedCheckpoint)
  assert.ok(live.some(step => step.target === '#creative-drop-zone'))
  assert.ok(live.some(step => step.type === 'WAIT_FOR_CREATIVE_REVIEW'))
  assert.equal(live.some(step => step.target === '[data-demo="autopilot-source-ai"]'), false)
  assert.match(engine, /id: `demo-\$\{briefId\}-\$\{formatId\}`/)
  assert.match(overlay, /Đang xử lý…/)
  assert.match(overlay, /role="status"/)
})

test('Autopilot demo lets users choose UI tour or interactive walkthrough immediately', () => {
  assert.match(engine, /title: 'Khởi động tour Campaign Autopilot'/)
  assert.match(engine, /\{ label: 'Tour giao diện', variant: 'outline', action: 'tour' \}/)
  assert.match(engine, /\{ label: 'Walkthrough tương tác', variant: 'primary', action: 'live' \}/)
  assert.match(
    engine,
    /setSteps\(tourModeRef\.current === 'autopilot'[\s\S]*?\[\.\.\.AUTOPILOT_TOUR_STEPS\][\s\S]*?\[\.\.\.STAGE1_STEPS\]/,
  )
})

test('mobile tour guidance uses target-aware docking with manual move and collapse controls', () => {
  assert.match(overlay, /data-demo="mobile-guide-box"/)
  assert.match(overlay, /data-mobile-dock=\{resolvedDock\}/)
  assert.match(overlay, /targetMidpoint < vh \/ 2 \? 'bottom' : 'top'/)
  assert.match(overlay, /window\.visualViewport\?\.addEventListener\('resize'/)
  assert.match(overlay, /ResizeObserver/)
  assert.match(overlay, /Di chuyển hướng dẫn xuống dưới/)
  assert.match(overlay, /Thu gọn hướng dẫn/)
  assert.match(overlay, /max-h-\[36dvh\]/)
  assert.match(overlay, /!manualDock && targetRect && dock === 'bottom'/)
  assert.doesNotMatch(overlay, /setPos\(\{ top: 10, left \}\)/)
})

test('narrow mobile workspaces keep header, crop actions, review dock, and artifact navigation reachable', () => {
  assert.match(topBar, /px-2 sm:gap-3 sm:px-5/)
  assert.match(topBar, /hidden min-\[400px\]:inline/)
  assert.match(cropModal, /sm:flex-row/)
  assert.match(cropModal, /onPointerDown/)
  assert.match(cropModal, /window\.addEventListener\('pointermove'/)
  assert.match(autopilot, /Hướng dẫn review/)
  assert.match(autopilot, /hidden max-w-3xl text-xs leading-5 text-amber-800 sm:block/)
  assert.match(workspacePane, /data-demo="artifact-nav-scroll"/)
  assert.match(workspacePane, /bg-gradient-to-l from-slate-50/)
})

test('technical document keeps the removed evidence content out and provides reliable Agent navigation', () => {
  assert.doesNotMatch(docs, /id="evidence"/)
  assert.match(docs, /href="\/agent\?from=docs" id="agent-entry-link"/)
  assert.doesNotMatch(docs, /agent-entry-link.*preventDefault|window\.location\.assign/)
})

test('technical document distinguishes the live feedback foundation from later learning stages', () => {
  assert.match(docs, /id="feedback-loop"/)
  assert.match(docs, /Feedback tại điểm quyết định/)
  assert.match(docs, /HITL adjudication/)
  assert.match(docs, /SFT · DPO · RLHF \/ RLAIF/)
  assert.match(docs, /Feedback hiện tại không tự sửa campaign/)
  assert.match(docs, /Review queue, automated dataset-candidate pipeline/)
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
