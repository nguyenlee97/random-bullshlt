import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import {
  MANAGE_PATH,
  agentConversationId,
  agentEntryMode,
  agentEntryUrl,
  agentPath,
  authReturnTo,
  hasAgentIntent,
  parseAppRoute,
} from '../src/lib/publicExperience.js'
import { AUTOPILOT_TOUR_STEPS } from '../src/demo/autopilotTour.js'
import { buildAutopilotLiveSteps } from '../src/demo/autopilotWalkthrough.js'
import {
  compatiblePlacementIndexes,
  samplePlacementIndexes,
  supportedPlacementIndexes,
} from '../src/demo/demoPlacementCompatibility.js'
import { calculateCoverCrop } from '../src/demo/demoCreativeFit.js'
import { DEMO_BRIEFS, getDemoDateRange, pickRandomBrief } from '../src/demo/demoScripts.js'

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
const nginx = read('../nginx.conf')
const styles = read('../src/index.css')
const api = read('../src/api/agentApi.js')
const chatHook = read('../src/hooks/useChat.js')

test('public landing and agent modes have canonical SPA routes', () => {
  assert.equal(hasAgentIntent({ pathname: '/', search: '' }), false)
  assert.equal(hasAgentIntent({ pathname: '/home', search: '' }), false)
  assert.equal(hasAgentIntent({ pathname: '/manage', search: '' }), true)
  assert.equal(hasAgentIntent({ pathname: '/workspace', search: '' }), true)
  assert.equal(hasAgentIntent({ pathname: '/agent', search: '' }), true)
  assert.equal(hasAgentIntent({ pathname: '/', search: '?conversation=conv_123' }), true)
  assert.equal(hasAgentIntent({ pathname: '/', search: '?auth=success' }), true)
  assert.equal(agentEntryMode({ pathname: '/agent', search: '' }), 'copilot')
  assert.equal(agentEntryMode({ pathname: '/agent/autopilot', search: '' }), 'autopilot')
  assert.equal(agentEntryMode({ pathname: '/agent', search: '?mode=copilot' }), 'copilot')
  assert.equal(agentEntryMode({ pathname: '/', search: '?mode=unknown' }), '')
  assert.equal(agentPath('guided'), '/agent')
  assert.equal(agentPath('autopilot'), '/agent/autopilot')
  assert.equal(agentPath('guided', 'conv / 123'), '/agent/copilot/history/conv%20%2F%20123')
  assert.equal(agentPath('autopilot', 'conv_456'), '/agent/autopilot/history/conv_456')
  assert.equal(
    agentConversationId({ pathname: '/agent/autopilot/history/conv_456', search: '' }),
    'conv_456',
  )
  assert.deepEqual(
    parseAppRoute({ pathname: '/manage', search: '' }),
    { surface: 'manage', mode: '', conversationId: '' },
  )
  assert.deepEqual(
    parseAppRoute({ pathname: '/workspace', search: '' }),
    { surface: 'manage', mode: '', conversationId: '' },
  )
  assert.equal(MANAGE_PATH, '/manage')
  assert.deepEqual(
    parseAppRoute({ pathname: '/agent/copilot/history/conv%20123', search: '' }),
    { surface: 'agent', mode: 'copilot', conversationId: 'conv 123' },
  )
  assert.deepEqual(
    parseAppRoute({ pathname: '/agent/copilot/history/conv_123', search: '?mode=autopilot' }),
    { surface: 'agent', mode: 'copilot', conversationId: 'conv_123' },
  )
  assert.equal(
    agentEntryUrl({ pathname: '/', search: '?tour=copilot', hash: '' }, 'autopilot'),
    '/agent/autopilot',
  )
  assert.equal(
    agentEntryUrl({ pathname: '/', search: '?mode=copilot&tour=copilot', hash: '' }),
    '/agent',
  )
  assert.match(app, /<PublicLanding/)
  assert.match(app, /agentEntryUrl\(window\.location, mode\)/)
  assert.match(app, /const nextUrl = mode \? agentEntryUrl\(window\.location, mode\) : MANAGE_PATH/)
  assert.match(app, /route\.surface === 'manage'[\s\S]*window\.history\.replaceState\(\{\}, '', `\$\{MANAGE_PATH\}/)
  assert.match(app, /agentPath\(context\.experience_mode, context\.conversation_id \|\| conversationId\)/)
  assert.match(app, /pendingEntryMode/)
  assert.match(app, /pendingEntryStartRef/)
  assert.match(app, /landingEntryAttemptRef/)
  assert.match(app, /entryIsStale/)
  assert.match(app, /setPendingConversationId\(route\.conversationId\)/)
  assert.match(app, /startCampaign\(mode === 'autopilot' \? 'autopilot' : 'guided', attempt\)/)
  assert.match(app, /archiveIfStale/)
  assert.match(app, /AgentAPI\.archiveConversation\(context\.conversation_id\)/)
  assert.match(app, /pendingConversationId/)
  assert.match(app, /window\.history\.replaceState\(\{\}, '', `\$\{HOME_PATH\}/)
  assert.match(app, /const handleReset[\s\S]*agentPath\(routeMode\)[\s\S]*newChat\(/)
  assert.match(nginx, /location = \/agent\/autopilot/)
  assert.match(nginx, /location ~ \^\/agent\/\(copilot\|autopilot\)\/history\/\[\^\/\]\+\/\?\$/)
  assert.match(nginx, /location \/agent\/ \{[\s\S]*proxy_pass/)
})

test('Zalo callback return path retains conversation and hash while removing callback residue', () => {
  assert.equal(
    authReturnTo({ pathname: '/agent/copilot/history/abc', search: '?auth=ok&theme=dark', hash: '#workspace' }),
    '/agent/copilot/history/abc?theme=dark#workspace',
  )
})

test('landing v3 implements the handed-off structure, assets, and production navigation', () => {
  assert.match(landing, /CampaignConstellation/)
  assert.match(landing, /campaign-stage/)
  assert.match(landing, /campaign-agent-core/)
  assert.match(landing, /\/brand\/advertising-agent-mascot\.png/)
  assert.equal(existsSync(new URL('../public/brand/advertising-agent-mascot.png', import.meta.url)), true)
  assert.doesNotMatch(landing, /function SignalRibbon|<SignalRibbon/)
  assert.doesNotMatch(landing, /<LandingProof/)
  assert.match(landing, /data-section="01"[\s\S]*data-section="02"[\s\S]*data-section="03"[\s\S]*data-section="04"[\s\S]*data-section="05"/)
  for (const id of ['tools', 'experience', 'error', 'slow']) {
    assert.match(landing, new RegExp(`id: '${id}'`))
  }
  for (const asset of ['card-marketer-scene.png', 'card-sales-scene.png', 'card-manager-scene2.png']) {
    assert.match(landing, new RegExp(asset.replace('.', '\\.')))
    assert.equal(existsSync(new URL(`../public/landing/personas/${asset}`, import.meta.url)), true)
  }
  assert.match(landing, /CampaignTruthVisual/)
  assert.match(landing, /\['06', 'Performance'/)
  assert.match(landing, /landing-manifesto-chapter/)
  assert.match(landing, /IntersectionObserver/)
  assert.match(landing, /data-scroll-reveal/)
  assert.match(landing, /Dual-Surface Experience/)
  assert.match(landing, /Safety & Privacy by Design/)
  assert.match(landing, /mode-visual-copilot/)
  assert.match(landing, /mode-visual-autopilot/)
  assert.match(landing, /<em>chuyển động\.<\/em>/)
  assert.doesNotMatch(landing, /310 segments/)
  assert.match(landing, /VITE_ADSPILOT_URL \|\| 'https:\/\/adspilot\.pawgrammers\.io\.vn'/)
  assert.match(landing, /VITE_ANALYTICS_URL \|\| 'https:\/\/analytics\.pawgrammers\.io\.vn'/)
  assert.doesNotMatch(landing, /\{ label: 'Audience', href:/)
  assert.doesNotMatch(landing, /\{ label: 'Publisher', href:/)
  assert.doesNotMatch(landing, /TourCompleteModal|Tour hoàn tất|updateTourQuery/)
  assert.match(landing, /<LandingHero onEnterAgent=\{onEnterAgent\} onOpenDemo=\{onOpenDemo\} \/>/)
  assert.match(landing, /<LandingModes onEnterAgent=\{enterMode\} onOpenDemo=\{onOpenDemo\} \/>/)
  assert.match(landing, /<LandingFinalCta onEnterAgent=\{onEnterAgent\} \/>/)
  assert.match(landing, /onEnterAgent\(mode\)/)
  assert.match(landing, /data-ecosystem-index=\{index\}/)
  assert.match(landing, /\/tech-docs\.html/)
  assert.match(landing, /landing-menu-toggle/)
  assert.match(landing, /aria-controls="landing-mobile-menu"/)
  assert.match(landing, /aria-expanded=\{mobileMenuOpen\}/)
  assert.match(landing, /Mở menu điều hướng/)
  assert.match(landing, /Đóng menu điều hướng/)
  assert.match(landing, /closeOnOutsidePress/)
  assert.match(landing, /closeOnFocusOutside/)
  assert.match(app, /startGuidedDemo/)
  assert.match(app, /pendingDemoMode/)
  assert.match(app, /enterAgentForDemo/)
  assert.match(app, /window\.history\.pushState\(\{\}, '', agentEntryUrl\(window\.location, demoMode\)\)/)
  assert.match(app, /<PublicLanding onEnterAgent=\{enterAgent\} onOpenDemo=\{enterAgentForDemo\} \/>/)
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
  assert.match(app, /onPrepareLive=\{prepareGuidedTour\}/)
  assert.match(app, /const prepareGuidedTour[\s\S]*agentPath\(routeMode\)[\s\S]*return handleReset\(\)/)
  assert.match(engine, /await onPrepareLive\?\.\(\)/)
  assert.doesNotMatch(app, /demo:new_chat/)
  assert.doesNotMatch(engine, /demo:new_chat/)
  assert.match(app, /window\.scrollTo\(\{ top: 0, left: 0, behavior: 'auto' \}\)/)
  assert.match(app, /appShellRef\.current\?\.scrollTo\(\{ top: 0, left: 0, behavior: 'auto' \}\)/)
  assert.match(app, /ref=\{appShellRef\} className="mobile-app-shell fixed inset-x-0 top-0 flex flex-col overflow-clip/)
})

test('Copilot creative walkthrough teaches assets and prompt composition without exposing provider or quota details', () => {
  assert.match(imageGenerator, /data-demo="creative-reference-assets"/)
  assert.match(scripts, /data-demo="creative-reference-assets"/)
  assert.match(scripts, /target: '#btn-compose-creative-prompt'/)
  assert.match(scripts, /target: '\[data-testid="creative-prompt-spec"\]'/)
  assert.doesNotMatch(imageGenerator, /image-quota-counter|image-quota-consent|image-quota-checkbox|GPT Image|OpenAI Creative/)
  assert.doesNotMatch(scripts, /image-quota-counter|image-quota-consent|image-quota-checkbox|GPT Image|quota/)
  assert.match(imageGenerator, /nextQueuedGenerations\(generationJobs\)/)
  assert.match(imageGenerator, /pendingGenerationCount >= MAX_PENDING_GENERATIONS/)
  assert.match(imageGenerator, /Hàng đợi đã đầy/)
  assert.match(imageGenerator, /AgentAPI\.listGeneratedImages\(\)/)
  assert.match(imageGenerator, /AgentAPI\.finalizeGeneratedImage\(pendingCrop\.jobId/)
  assert.doesNotMatch(imageGenerator, /if \(openaiCampaignFlow\) \{\s*\/\/ A generated image is a draft/)
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
  assert.match(engine, /state === 'upload_failed'/)
  assert.match(engine, /action: 'retry_previous_step'/)
  assert.match(scripts, /whenReviewState: 'blocked'/)
  assert.match(scripts, /retryPreviousStep: true/)
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

test('every walkthrough brief identifies the product, audience, and message', () => {
  for (const brief of DEMO_BRIEFS) {
    assert.match(brief.chatMessage, /Sản phẩm \/ dịch vụ:/)
    assert.match(brief.chatMessage, /Đối tượng mục tiêu:/)
    assert.match(brief.chatMessage, /Thông điệp chính:/)
    assert.match(brief.briefPatch.notes, /Sản phẩm \/ dịch vụ:/)
    assert.match(brief.briefPatch.notes, /Đối tượng mục tiêu:/)
  }
  const vietjet = DEMO_BRIEFS.find(brief => brief.id === 'vietjet')
  assert.match(vietjet.briefPatch.notes, /vé máy bay giá rẻ/)
  assert.match(vietjet.briefPatch.notes, /thích du lịch/)
})

test('Copilot and Autopilot request different mode-aware introductions', () => {
  assert.match(app, /boot\(experienceMode\)/)
  assert.match(chatHook, /AgentAPI\.boot\(experienceMode\)/)
  assert.match(api, /experience_mode: experienceMode === 'autopilot' \? 'autopilot' : 'guided'/)
  assert.match(api, /Bạn đang ở \*\*Campaign Autopilot\*\*/)
  assert.match(api, /Bạn đang ở \*\*Campaign Copilot\*\*/)
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
  assert.match(autopilot, /Sản phẩm\/dịch vụ, KPI và đối tượng mục tiêu/)
  assert.match(autopilot, /Upload khi đã có asset chính thức/)
  assert.match(autopilot, /openaiCampaignFlow \? 3 : 5/)
  assert.match(autopilot, /Bán tự động: Agent tự chọn Audience và targeting/)
  assert.match(autopilot, /Tự động hoàn toàn: Agent tự chọn audience liên quan/)
  assert.match(app, /openaiCampaignFlow=\{currentConversationModel === 'openai_gpt_5_4_mini'\}/)
})

test('Autopilot walkthrough auto-commits audience and targeting, then stops before launch', () => {
  const brief = pickRandomBrief(new Date(2026, 6, 23, 12, 0, 0))
  const live = buildAutopilotLiveSteps(brief, { creativeSource: 'ai_generate' })
  const types = live.map(step => step.type)

  assert.ok(types.includes('APPLY_AUTOPILOT_BRIEF'))
  assert.ok(types.includes('WAIT_FOR_AUTOPILOT_TASK'))
  const briefWait = live.find(step => step.type === 'WAIT_FOR_RESPONSE')
  assert.equal(
    briefWait.requiredSelector,
    '[data-demo="workspace-proposal-confirm"][data-workspace-field="brief"]',
  )
  assert.equal(types.includes('TRIM_AUTOPILOT_AUDIENCE'), false)
  assert.equal(types.includes('CHANGE_AUTOPILOT_TARGETING'), false)
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
  assert.match(engine, /step\.requiredSelector/)
  assert.match(engine, /step\.whenSelector/)
  assert.match(engine, /step\.ignoreWaitingReasons/)
  assert.match(engine, /step\.allowHandledTask/)
  assert.match(engine, /Brief chưa được tạo thành công/)
  assert.match(engine, /unexpected:\$\{taskKey\}/)
  assert.match(engine, /Brief cần thêm ngữ cảnh trước khi tìm audience/)
  assert.match(engine, /case 'TRIM_AUTOPILOT_AUDIENCE'/)
  assert.match(engine, /case 'CHANGE_AUTOPILOT_TARGETING'/)
  assert.match(engine, /case 'TRIM_AUTOPILOT_PLACEMENTS'/)

  assert.match(audienceStep, /data-demo="autopilot-audience-option"/)
  assert.match(targetingPanel, /data-demo="autopilot-targeting-option"/)
  assert.match(autopilotReview, /data-demo="autopilot-placement-option"/)
  assert.match(workspacePane, /data-demo="autopilot-editor-save"/)
  assert.match(assignmentEditor, /data-demo="autopilot-creative-assignment-editor"/)
  assert.match(autopilot, /data-demo="autopilot-review-approve"/)
  assert.match(autopilot, /data-demo="autopilot-creative-analysis-start"/)
  assert.match(autopilot, /data-autopilot-waiting-reason/)
  assert.match(autopilot, /data-demo="autopilot-plan-details"/)
  assert.match(autopilot, /data-demo="autopilot-technical-details"/)

  const analysisStart = live.find(
    step => step.type === 'CLICK_EL'
      && step.target === '[data-demo="autopilot-creative-analysis-start"]',
  )
  assert.ok(analysisStart)
  assert.equal(analysisStart.whenAutopilotTask, 'analyze_creatives')
  assert.equal(
    analysisStart.whenSelector,
    '[data-demo="autopilot-creative-analysis-start"]',
  )
  const analysisCompletionWait = live.find(
    step => step.type === 'WAIT_FOR_AUTOPILOT_TASK'
      && step.allowHandledTask
      && step.ignoreWaitingReasons?.includes('analysis_in_progress'),
  )
  assert.ok(analysisCompletionWait)
  assert.deepEqual(analysisCompletionWait.ignoreWaitingReasons, [
    'analysis_confirmation_required',
    'analysis_in_progress',
  ])

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

test('Autopilot upload walkthrough randomly samples creative-compatible placements', () => {
  const formats = [
    { formatId: 'znews-top-banner', width: 2224, height: 480, intendedFormat: 'banner' },
    { formatId: 'znews-side-banner', width: 736, height: 1456, intendedFormat: 'banner' },
  ]
  const candidates = [
    { size: '300x250', creativeContractId: 'display-box-300x250-v1' },
    { size: '1160x250', creativeContractId: 'znews-category-masthead-v1' },
    { size: '300x600', creativeContractId: 'display-halfpage-300x600-v1' },
  ]
  const picked = compatiblePlacementIndexes(candidates, formats, 2, () => 0)
  assert.equal(picked.length, 2)
  assert.deepEqual(new Set(picked), new Set([1, 2]))
  assert.deepEqual(samplePlacementIndexes([0, 1, 2, 3], 2, () => 0), [1, 2])
  assert.deepEqual(
    supportedPlacementIndexes(candidates, 2, () => 0),
    [1, 2],
  )

  const brief = pickRandomBrief(new Date(2026, 6, 23, 12, 0, 0))
  const trim = buildAutopilotLiveSteps(brief, { creativeSource: 'upload' })
    .find(step => step.type === 'TRIM_AUTOPILOT_PLACEMENTS')
  assert.ok(trim.creativeFormats.length > 0)
  assert.match(trim.title, /khớp creative/)
  assert.match(engine, /compatiblePlacementIndexes/)
  assert.match(engine, /supportedPlacementIndexes/)
  assert.match(autopilotReview, /data-zone-contract=/)
  assert.match(autopilotReview, /creativeRequirements/)
  assert.match(autopilotReview, /Kích thước/)
})

test('OpenAI walkthrough converts demo image bytes to the declared delivery dimensions', () => {
  assert.deepEqual(
    calculateCoverCrop(1024, 1024, 1504, 704, 'top'),
    { sx: 0, sy: 0, sw: 1024, sh: 479.3191489361702 },
  )
  assert.deepEqual(
    calculateCoverCrop(1024, 1024, 465, 1200, 'right'),
    { sx: 627.2, sy: 0, sw: 396.8, sh: 1024 },
  )
  assert.match(engine, /fitDemoCreative\(sourceBlob, meta\)/)
  assert.match(engine, /exactDimensionsVerified/)
  assert.match(engine, /isOpenAIWalkthroughModel\(conversationModelRef\.current\)/)
  assert.match(scripts, /cropAnchor: 'top'/)
  assert.match(scripts, /cropAnchor: 'right'/)
  assert.match(scripts, /cropAnchor: 'left'/)
})

test('Autopilot assignment editor restores the server recommendation and has no upload detour', () => {
  assert.match(app, /recommendedAssignments/)
  assert.match(assignmentEditor, /Dùng gán đề xuất/)
  assert.match(assignmentEditor, /checkAutopilotMismatch/)
  assert.match(autopilot, /Dùng đề xuất hoặc chỉnh phân bổ/)
  assert.doesNotMatch(autopilot, /Tải creative mới/)
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

test('Autopilot walkthrough pauses for creative analysis and assignment explanations', () => {
  const brief = pickRandomBrief(new Date(2026, 6, 23, 12, 0, 0))
  const live = buildAutopilotLiveSteps(brief, { creativeSource: 'ai_generate' })
  const analysisReadStep = live.find(
    step => step.type === 'TOOLTIP'
      && step.title === 'Phân tích creative trước khi gán',
  )
  const analysisResultStep = live.find(
    step => step.type === 'TOOLTIP'
      && step.title === 'Phân tích creative đã hoàn tất',
  )
  const assignmentReviewStep = live.find(
    step => step.type === 'TOOLTIP'
      && step.title === 'Kiểm tra gán creative trước khi lưu',
  )
  assert.ok(analysisReadStep)
  assert.ok(analysisResultStep)
  assert.ok(assignmentReviewStep)
  assert.match(analysisReadStep.text, /bấm \*\*Tiếp theo\*\*/)
  assert.match(analysisResultStep.text, /Gán creative/)
  assert.match(assignmentReviewStep.text, /chưa lưu/)
  assert.ok(live.some(
    step => step.type === 'WAIT_FOR_AUTOPILOT_TASK'
      && step.taskKeys.includes('assign_creatives')
      && step.allowHandledTask,
  ))
  assert.match(topBar, /tour-attention-button/)
  assert.match(styles, /@keyframes tour-attention-flash/)
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
  assert.match(topBar, /aria-label="Về trang quản lý campaign"/)
  assert.doesNotMatch(topBar, /tech-docs-btn|new-chat-btn|>Docs<|>Trang chủ</)
  const tourIndex = topBar.indexOf('id="demo-btn"')
  const historyIndex = topBar.indexOf('id="conversation-history-btn"')
  const resetIndex = topBar.indexOf('data-demo="reset-btn"')
  const accountIndex = topBar.lastIndexOf('<AccountMenu')
  assert.ok(tourIndex >= 0 && historyIndex > tourIndex)
  assert.ok(resetIndex > historyIndex)
  assert.ok(accountIndex > resetIndex)
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
  assert.match(docs, /href="\/home">← <span>Trang giới thiệu<\/span>/)
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
  assert.match(styles, /@media \(max-width:1050px\)/)
  assert.match(styles, /@media \(max-width:1040px\)/)
  assert.match(styles, /@media \(max-width:760px\)/)
  assert.match(styles, /@media \(max-width: 700px\)/)
  assert.match(styles, /@media \(max-width:560px\)/)
  assert.match(styles, /prefers-reduced-motion: reduce/)
  assert.match(styles, /campaign-stage \*/)
  assert.match(styles, /animation: none !important/)
  assert.match(styles, /scroll-snap-type:x mandatory/)
  assert.match(styles, /\.landing-desktop-nav-links \{ display:none; \}/)
  assert.match(styles, /\.landing-mobile-nav-panel:not\(\[hidden\]\)/)
  assert.match(styles, /\.landing-menu-toggle \{[\s\S]*width:44px/)
  assert.match(styles, /\.landing-agent-cta \{ display:none; \}/)
  assert.doesNotMatch(styles, /a\[data-ecosystem-index="0"\]::before/)
  assert.doesNotMatch(styles, /@media \(max-width:560px\) \{[^}]*nav a \{ display:none/)
  assert.match(styles, /@keyframes v3Spin360/)
  assert.match(styles, /@keyframes dvFlow/)
  assert.match(styles, /\.public-landing-v3 \.scroll-reveal/)
  assert.match(styles, /\.scroll-reveal\.is-visible/)
})
