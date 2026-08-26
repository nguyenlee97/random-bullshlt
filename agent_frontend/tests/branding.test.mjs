import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..', '..')

async function source(relativePath) {
  return readFile(path.join(root, relativePath), 'utf8')
}

const USER_FACING_FILES = [
  'agent/prompts/audience.py',
  'agent/prompts/brief.py',
  'agent/prompts/system.py',
  'agent/handlers/result.py',
  'agent/tools/registry.py',
  'agent_frontend/index.html',
  'agent_frontend/public/tech-docs.html',
  'agent_frontend/src/components/ChatPane/ChatComposer.jsx',
  'agent_frontend/src/components/ChatPane/index.jsx',
  'agent_frontend/src/demo/demoScripts.js',
  'agent_frontend/src/hooks/useChat.js',
  'agent_frontend/src/steps/SuccessStep.jsx',
  'backend/services/emailService.js',
  'backend/services/reportPDFGenerator.js',
]

test('user-facing surfaces use the Advertising Agent identity', async () => {
  for (const file of USER_FACING_FILES) {
    const contents = await source(file)
    assert.doesNotMatch(contents, /Camp Ads Agent|CAMP ADS AGENT/, `${file} still exposes the old product name`)
  }

  assert.match(await source('agent_frontend/index.html'), /Advertising Agent/)
  assert.match(await source('backend/services/emailService.js'), /\[Advertising Agent\]/)
  assert.match(await source('backend/services/reportPDFGenerator.js'), /ADVERTISING AGENT/)
})

test('exported artifacts use the blue brand palette', async () => {
  const email = await source('backend/services/emailService.js')
  const pdf = await source('backend/services/reportPDFGenerator.js')
  const docs = await source('agent_frontend/public/tech-docs.html')

  assert.match(email, /#0068ff/)
  assert.match(pdf, /primary:\s+'#0068ff'/)
  assert.match(docs, /--accent2:#0068ff/)
  assert.doesNotMatch(`${pdf}\n${docs}`, /#4f46e5|#7c3aed|#4dd4ac/)
})

test('external platform links use product-neutral labels', async () => {
  const visibleCopy = await Promise.all([
    source('agent/handlers/result.py'),
    source('agent/tools/registry.py'),
    source('agent_frontend/src/components/ChatPane/ChatComposer.jsx'),
    source('agent_frontend/src/demo/demoScripts.js'),
    source('agent_frontend/src/hooks/useChat.js'),
    source('agent_frontend/src/steps/SuccessStep.jsx'),
  ])

  assert.doesNotMatch(visibleCopy.join('\n'), />?AdsPilot<?/)
  assert.match(visibleCopy.join('\n'), /Trình quản lý quảng cáo|trình quản lý quảng cáo/)
})

test('core mode controls keep mobile layout and accessible names', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const selector = await source('agent_frontend/src/components/CampaignHome.jsx')
  const topBar = await source('agent_frontend/src/components/TopBar.jsx')
  const composer = await source('agent_frontend/src/components/ChatPane/ChatComposer.jsx')
  const autopilot = await source('agent_frontend/src/components/AutopilotPanel.jsx')

  assert.match(selector, /min-h-screen/)
  assert.match(selector, /sm:grid-cols-2/)
  assert.match(app, /md:hidden/)
  assert.match(app, /flex-col md:flex-row/)
  assert.match(app, /role="tablist"/)
  assert.match(app, /aria-selected=/)
  assert.match(selector, /Tạo campaign mới/)
  assert.doesNotMatch(app, /<ModeSwitcher/)
  assert.match(topBar, /aria-label="Về trang quản lý campaign"/)
  assert.match(topBar, /id="demo-btn"[\s\S]*id="conversation-history-btn"[\s\S]*data-demo="reset-btn"[\s\S]*<AccountMenu/)
  assert.doesNotMatch(topBar, /tech-docs-btn|new-chat-btn/)
  assert.match(composer, /aria-label="Tin nhắn gửi Advertising Agent"/)
  assert.match(composer, /aria-label=\{busy \? 'Advertising Agent đang xử lý' : 'Gửi tin nhắn'\}/)
  assert.match(autopilot, /aria-label="Tạm dừng Autopilot"/)
  assert.match(autopilot, /aria-label="Hủy Autopilot run"/)
})

test('agent credential stays behind the frontend proxy', async () => {
  const api = await source('agent_frontend/src/api/agentApi.js')
  const dockerfile = await source('agent_frontend/Dockerfile')
  const nginx = await source('agent_frontend/nginx.conf')
  const compose = await source('docker-compose.yml')
  const productionEnv = await source('agent_frontend/.env.production')

  assert.doesNotMatch(api, /VITE_AGENT_API_KEY|X-API-Key/)
  assert.doesNotMatch(dockerfile, /VITE_AGENT_API_KEY/)
  assert.match(nginx, /proxy_set_header X-API-Key "\$\{AGENT_API_KEY\}"/)
  assert.match(compose, /VITE_AGENT_URL: \/agent/)
  assert.match(productionEnv, /^VITE_AGENT_URL=\/agent$/m)
  assert.doesNotMatch(productionEnv, /^VITE_AGENT_URL=https?:\/\//m)
  assert.match(compose, /127\.0\.0\.1:27017:27017/)
})

test('local Compose includes AdsPilot and truthful mock-site ad delivery', async () => {
  const compose = await source('docker-compose.yml')
  const dockerfile = await source('agent_frontend/Dockerfile')
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const znewsApi = await source('znews_replicate/api.js')
  const znewsCategoryCss = await source('znews_replicate/category-style.css')
  const baomoiApi = await source('baomoi_replicate/api.js')
  const zingmp3Api = await source('zingmp3_replicate/api.js')

  assert.match(compose, /127\.0\.0\.1:5173:80/)
  assert.match(compose, /127\.0\.0\.1:5176:80/)
  assert.match(compose, /127\.0\.0\.1:5177:80/)
  assert.match(compose, /127\.0\.0\.1:5178:80/)
  assert.match(compose, /SITE_URL_MODE=local/)
  assert.match(compose, /VITE_ADSPILOT_URL: http:\/\/localhost:5173/)
  assert.match(dockerfile, /ARG VITE_ADSPILOT_URL=/)
  assert.match(panel, /import\.meta\.env\.VITE_ADSPILOT_URL/)
  assert.match(znewsCategoryCss, /\.np6-topic-masthead \{[\s\S]*?margin: 82px auto 0 !important;/)
  assert.match(znewsCategoryCss, /\.np6-topic-masthead \{[\s\S]*?float: none !important;/)
  for (const api of [znewsApi, baomoiApi, zingmp3Api]) {
    assert.match(api, /ALLOW_FALLBACK_ADS/)
    assert.match(api, /reason: 'no_active_campaign'/)
    assert.match(api, /reason: 'backend_unreachable'/)
  }
})

test('campaign strategy simulator is integrated into Autopilot', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const simulator = await source('agent_frontend/src/components/StrategySimulator.jsx')
  const api = await source('agent_frontend/src/api/agentApi.js')

  assert.match(panel, /<StrategySimulator/)
  assert.match(simulator, /Kịch bản phân bổ theo brief/)
  assert.match(simulator, /Độ phủ dự kiến/)
  assert.match(simulator, /CPM giả định/)
  assert.match(simulator, /Số liệu này được tính như thế nào/)
  assert.match(simulator, /Chọn phương án này/)
  assert.match(simulator, /triệu \$\{unit\}/)
  assert.match(simulator, /nghìn \$\{unit\}/)
  assert.match(api, /selectAutopilotStrategy/)
  assert.match(api, /\/strategy`/)
  assert.match(panel, /Kết quả Autopilot/)
  assert.match(panel, /Chi tiết kỹ thuật/)
  assert.match(panel, /Run trace:/)
  assert.match(panel, /run\.trace_id \|\| run\.run_id/)
  assert.match(panel, /RAG\/rerank/)
})

test('Autopilot requires an explicit creative source and supports automatic generation', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const api = await source('agent_frontend/src/api/agentApi.js')

  assert.match(panel, /Tôi sẽ tải creative lên/)
  assert.match(panel, /Để AI tự tạo creative/)
  assert.match(panel, /creativeSource === 'ai_generate'/)
  assert.match(panel, /nguồn creative \(tải lên hoặc AI tự tạo\)/)
  assert.match(panel, /disabled=\{loading \|\| prerequisitesLoading\}/)
  assert.doesNotMatch(panel, /disabled=\{!briefReady \|\| !creativeSource/)
  assert.match(panel, /startAutopilot\(policy, creativeSource, startKey, \{/)
  assert.match(panel, /creative direction cho AI/)
  assert.match(panel, /assetIds: \[\.\.\.creativeAssetIds\]/)
  assert.match(api, /creative_source: creativeSource/)
  assert.match(api, /creative_direction: creativeInput\.direction/)
  assert.match(api, /autopilot-start:\$\{SESSION_ID\}:\$\{creativeSource\}:\$\{startKey/)
})

test('Autopilot exposes a placement-aware bounded creative format plan', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const docs = await source('agent_frontend/public/tech-docs.html')

  assert.match(panel, /plan_creative_formats/)
  assert.match(panel, /Kế hoạch creative theo placement/)
  assert.match(panel, /formatPlan\?\.max_assets/)
  assert.match(panel, /formatPlan\.estimated_provider_calls/)
  assert.match(docs, /bounded image generation/)
  assert.doesNotMatch(docs, /Multi-format generation và creative variants vẫn là roadmap/)
})

test('Autopilot presents ordered stages, generated assets, and only unlocks strategy at review', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const simulator = await source('agent_frontend/src/components/StrategySimulator.jsx')

  assert.match(panel, /const TASK_ORDER = \[/)
  assert.match(panel, /const LEGACY_AUTOPILOT_STAGES = \[/)
  assert.match(panel, /const DEMO_V2_AUTOPILOT_STAGES = \[/)
  assert.match(panel, /run\?\.flow_version === 'demo_v2'/)
  assert.match(panel, /Xem toàn bộ \{orderedTasks\.length\} bước theo thứ tự/)
  assert.match(panel, /Creative đã tạo/)
  assert.match(panel, /<img src=\{file\.url\}/)
  assert.match(panel, /const strategyCanChange = waiting\?\.key === 'generate_strategy'/)
  assert.match(panel, /strategyTask\?\.status === 'waiting_review'/)
  assert.match(panel, /Phương án chỉ có thể thay đổi khi Autopilot đang dừng tại một điểm review/)
  assert.doesNotMatch(panel, /rejectAndEdit/)
  assert.match(panel, /Order đang chờ kích hoạt nên test site chưa hiển thị quảng cáo/)
  assert.match(panel, /https:\/\/adspilot\.pawgrammers\.io\.vn/)
  assert.match(simulator, /selectionHint/)
})

test('Autopilot presents artifacts without Guided workflow controls', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const workspace = await source('agent_frontend/src/components/WorkspacePane/index.jsx')
  const creative = await source('agent_frontend/src/steps/CreativeStep.jsx')
  const compatibility = await source('agent_frontend/src/lib/creativeCompatibility.js')
  const chat = await source('agent_frontend/src/hooks/useChat.js')
  const topbar = await source('agent_frontend/src/components/TopBar.jsx')
  assert.match(app, /autopilotMode=\{experienceMode === 'autopilot'\}/)
  assert.match(app, /silent: true/)
  assert.match(app, /markApproved: false/)
  assert.match(workspace, /Điều hướng campaign artifacts/)
  assert.match(workspace, /!autopilotMode && <WorkFoot/)
  assert.match(workspace, /Phân tích, lưu & quay lại Autopilot/)
  assert.match(workspace, /Quay lại chưa lưu/)
  assert.match(creative, /brand-format-kích-thước\.png/)
  assert.match(compatibility, /MAX_AUTOPILOT_RATIO_DIFF = 0\.15/)
  assert.match(chat, /const silent = options\.silent === true/)
  assert.doesNotMatch(topbar, /Minimax-M2\.5/)
})

test('strict Autopilot reviews expose artifacts and edit without rejecting the run', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const review = await source('agent_frontend/src/components/AutopilotReview.jsx')
  const app = await source('agent_frontend/src/App.jsx')

  assert.match(panel, /<AutopilotReview/)
  assert.match(panel, /Chỉnh audience/)
  assert.match(panel, /Chỉnh targeting/)
  assert.match(panel, /Tải creative lên/)
  assert.doesNotMatch(panel, /Tải creative mới/)
  assert.match(panel, /Dùng đề xuất hoặc chỉnh phân bổ/)
  assert.match(panel, /Hủy run/)
  assert.doesNotMatch(panel, /Từ chối & tải Creative/)
  assert.match(review, /Nội dung cần review/)
  assert.match(review, /Đề xuất trực tiếp/)
  assert.match(review, /Liên quan để mở rộng/)
  assert.doesNotMatch(review, /Catalog không bị cắt/)
  assert.match(review, /Format Autopilot|Format yêu cầu/)
  assert.match(app, /openAutopilotAudienceEditor/)
  assert.match(app, /openAutopilotAssignmentEditor/)
  assert.match(app, /commitWorkspace\('assignments'/)
  assert.match(app, /autopilotEditorArtifactRef\.current === 'assignments'/)
  assert.match(app, /prev\.setup\?\.assignments \|\| \{\}/)
  assert.match(app, /result\?\.shouldAdvance/)
})

test('campaign mode is fixed at homepage while Autopilot may open its data editor', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')

  assert.match(app, /data-mode-canvas="guided"/)
  assert.match(app, /data-mode-canvas="autopilot"/)
  assert.match(app, /Autopilot is a sibling canvas, not a banner above the workspace/)
  assert.match(app, /Quay lại Autopilot/)
  assert.match(app, /startCampaign/)
  assert.doesNotMatch(app, /<ModeSwitcher/)
  assert.match(app, /bootedRef\.current/)
  assert.match(panel, /sticky top-0/)
  assert.match(panel, /sticky bottom-2/)
})

test('workspace proposals have one durable decision lifecycle', async () => {
  const blocks = await source('agent_frontend/src/blocks/BlockRenderer.jsx')
  const app = await source('agent_frontend/src/App.jsx')
  const api = await source('agent_frontend/src/api/agentApi.js')
  assert.match(blocks, /agent:workspace_proposal_result/)
  assert.match(blocks, /Đã áp dụng vào workspace/)
  assert.match(blocks, /Đã bỏ qua đề xuất/)
  assert.match(blocks, /Đề xuất đã lỗi thời vì workspace có thay đổi mới/)
  assert.match(app, /persisted\?\.conflict \? 'superseded' : 'failed'/)
  assert.match(api, /block\.type === 'workspace_proposal'/)
})

test('Autopilot keeps one stable event stream across parent renders', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  assert.match(panel, /workspaceRefreshRef = useRef\(onWorkspaceRefresh\)/)
  assert.match(panel, /workspaceRefreshRef\.current\?\.\(\) \|\| AgentAPI\.getWorkspace\(\)/)
  assert.match(panel, /\}, \[loadPrerequisites, run\?\.run_id\]\)/)
})

test('Autopilot never persists an unapproved chat brief or retries it unchanged', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const api = await source('agent_frontend/src/api/agentApi.js')
  assert.doesNotMatch(panel, /commitWorkspace\('brief', brief\)/)
  assert.match(panel, /getPendingWorkspaceProposals/)
  assert.match(panel, /Brief đang chờ duyệt/)
  assert.match(panel, /Mở Chat để duyệt/)
  assert.match(panel, /disabled=\{loading \|\| \(retryAction && !retryReady\) \|\| !audienceReviewReady \|\| \(waiting\.key === 'plan_placement_intent' && !placementSelection\.length\)\}/)
  assert.match(api, /workspace\/proposals\?session_id=/)
})

test('placement review edits the shortlist instead of redirecting to Brief', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const review = await source('agent_frontend/src/components/AutopilotReview.jsx')
  const api = await source('agent_frontend/src/api/agentApi.js')
  assert.match(panel, /selectAutopilotPlacements/)
  assert.doesNotMatch(panel, /Sửa Brief đầu vào/)
  assert.match(review, /ad zone Agent đề xuất/)
  assert.doesNotMatch(review, /mặc định top 6|tối đa 6 zone cuối/)
  assert.match(panel, /defaultPlacementSelection/)
  assert.match(review, /synthetic_inventory_v2/)
  assert.match(api, /placement-intent/)
})

test('Autopilot targeting repair opens the targeting controls immediately', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const workspace = await source('agent_frontend/src/components/WorkspacePane/index.jsx')
  const audience = await source('agent_frontend/src/steps/AudienceStep.jsx')
  const targeting = await source('agent_frontend/src/components/TargetingPanel.jsx')
  assert.match(app, /autopilotEditorArtifact=\{autopilotEditorArtifact\}/)
  assert.match(workspace, /expandTargeting=\{autopilotMode && autopilotEditorArtifact === 'targeting'\}/)
  assert.match(audience, /autoExpand=\{expandTargeting\}/)
  assert.match(targeting, /if \(autoExpand\) setExpanded\(true\)/)
  assert.match(targeting, /ADVANCED_TARGETING_KEYS\.some/)
  assert.match(targeting, /if \(hasAdvancedSelection\) setAdvExpanded\(true\)/)
})

test('Autopilot hides stale review actions after a terminal run', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  assert.match(panel, /const runTerminal = \['completed', 'cancelled', 'failed'\]\.includes\(run\?\.status\)/)
  assert.match(panel, /const waiting = runTerminal \? null/)
  assert.match(panel, /if \(!run\?\.run_id \|\| \['completed', 'cancelled', 'failed'\]\.includes\(run\.status\)\) return/)
})

test('Autopilot chat is state-aware and reuses the full report module', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const composer = await source('agent_frontend/src/components/ChatPane/ChatComposer.jsx')
  const outcome = await source('agent_frontend/src/components/AutopilotOutcome.jsx')
  assert.match(app, /Autopilot đang thực thi và sở hữu workspace/)
  assert.match(app, /mode: 'review'/)
  assert.match(app, /mode: 'readonly'/)
  assert.match(composer, /Đồng ý, tiếp tục/)
  assert.match(composer, /Chat tạm khóa trong khi Autopilot thực thi/)
  assert.match(outcome, /import ReportStep from '@\/steps\/ReportStep'/)
  assert.doesNotMatch(outcome, /lazy\(\(\) => import\('@\/steps\/ReportStep'\)\)/)
  assert.match(outcome, /data-testid="autopilot-report-module"/)
  const reportStep = await source('agent_frontend/src/steps/ReportStep.jsx')
  assert.match(reportStep, /Tải PDF đầy đủ \(6 báo cáo\)/)
  assert.match(reportStep, /api\/reports\/export\/.*\/pdf/)
  assert.match(outcome, /onSendChat=\{onSendReportQuestion\}/)
  assert.doesNotMatch(outcome, /PerformanceReportState/)
  assert.match(app, /onReportActivate=\{initializeReport\}/)
})

test('frontend rebuilds cannot turn missing chunks into a blank page', async () => {
  const nginx = await source('agent_frontend/nginx.conf')
  const deployWorkflow = await source('.github/workflows/deploy-frontend-production.yml')
  const main = await source('agent_frontend/src/main.jsx')
  const boundary = await source('agent_frontend/src/components/AppRuntimeBoundary.jsx')
  const workspace = await source('agent_frontend/src/components/WorkspacePane/index.jsx')
  const blocks = await source('agent_frontend/src/blocks/BlockRenderer.jsx')

  assert.match(nginx, /location \/assets\//)
  assert.match(nginx, /try_files \$uri =404/)
  assert.match(nginx, /no-store, no-cache, must-revalidate/)
  assert.match(nginx, /location = \/agent \{[\s\S]*?try_files \/index\.html =404/)
  assert.match(main, /<AppRuntimeBoundary>/)
  assert.match(boundary, /Tải lại giao diện/)
  assert.doesNotMatch(workspace, /lazy\(/)
  assert.doesNotMatch(blocks, /lazy\(/)
  assert.match(deployWorkflow, /find "\$release_path" -type d -exec chmod 0755/)
  assert.match(deployWorkflow, /find "\$release_path" -type f -exec chmod 0644/)
  assert.match(deployWorkflow, /grep '\^\/assets\/'/)
  assert.match(deployWorkflow, /https:\/\/agent\.pawgrammers\.io\.vn\$\{asset_path\}/)
})

test('report analysis answers import the icon used by their rich block', async () => {
  const blocks = await source('agent_frontend/src/blocks/BlockRenderer.jsx')
  assert.match(blocks, /import \{[^}]*BarChart[^}]*\} from 'lucide-react'/s)
  assert.match(blocks, /case 'report_analysis':\s+return <ReportAnalysisBlock block=\{block\} \/>/)
  assert.match(blocks, /<BarChart className=/)
})

test('demo fallback remains internal, timestamped, and cannot mutate workspace', async () => {
  const api = await source('agent_frontend/src/api/agentApi.js')
  const chat = await source('agent_frontend/src/hooks/useChat.js')
  const app = await source('agent_frontend/src/App.jsx')
  assert.doesNotMatch(api, /Chế độ demo dự phòng/)
  assert.match(api, /workspace_update: null/)
  assert.match(api, /timestamp: response\?\.timestamp \|\| new Date\(\)\.toISOString\(\)/)
  assert.match(api, /fallback_mode: true/)
  assert.match(api, /brief chưa được lưu/)
  assert.match(api, /audience chưa được lưu/)
  assert.match(api, /setup chưa được lưu/)
  assert.match(api, /không thể xác minh kết quả campaign/)
  assert.match(api, /báo cáo chưa được khởi tạo/)
  assert.match(chat, /Không thể tạo chiến dịch mới/)
  assert.match(chat, /return context/)
  assert.match(app, /if \(!context\) return/)
})

test('chat hides internal tool and model metadata while preserving retry', async () => {
  const bubble = await source('agent_frontend/src/components/ChatPane/MessageBubble.jsx')
  assert.doesNotMatch(bubble, /function ModelBadge/)
  assert.doesNotMatch(bubble, /tool=\{message\.metadata\.tool\}/)
  assert.doesNotMatch(bubble, /model=\{message\.metadata\.model\}/)
  assert.match(bubble, /function RetryAction/)
  assert.match(bubble, /hasReportAnalysis/)
  assert.match(bubble, /!hasReportAnalysis && message\.content/)
})

test('report answers use adaptive metrics and suppress meaningless trend deltas', async () => {
  const blocks = await source('agent_frontend/src/blocks/BlockRenderer.jsx')
  const thread = await source('agent_frontend/src/components/ChatPane/ChatThread.jsx')
  assert.match(blocks, /useSingleColumn/)
  assert.match(blocks, /String\(m\.delta \|\| ''\)\.length > 22/)
  assert.match(blocks, /break-words/)
  assert.match(blocks, /showTrend/)
  assert.match(blocks, /<span className="min-w-0 break-words">\{delta\}<\/span>/)
  assert.doesNotMatch(blocks, /font-semibold flex-shrink-0/)
  assert.match(blocks, /min-w-\[420px\]/)
  assert.match(thread, /showSuggestions=\{msg\.id === lastAssistantId\}/)
})

test('legacy zone fallbacks resolve navigation from deployment environment', async () => {
  const zones = await source('agent_frontend/src/data/zones.js')
  const dockerfile = await source('agent_frontend/Dockerfile')
  assert.match(zones, /VITE_BACKEND_URL/)
  assert.match(zones, /VITE_ZNEWS_URL/)
  assert.match(zones, /VITE_BAOMOI_URL/)
  assert.match(zones, /VITE_ZINGMP3_URL/)
  assert.match(zones, /export const ALL_ZONES = RAW_ZONES\.map/)
  assert.match(dockerfile, /ARG VITE_ZNEWS_URL=/)
})

test('campaign homepage exposes delayed Zalo continuity without duplicating the OA link flow', async () => {
  const home = await source('agent_frontend/src/components/CampaignHome.jsx')
  assert.doesNotMatch(home, /import ZaloOACompanion/)
  assert.match(home, /function ZaloContinuityNudge/)
  assert.match(home, /window\.setTimeout\(\(\) => setVisible\(true\), 2600\)/)
  assert.match(home, /onLinkZalo/)
  assert.match(home, /onOpenZaloOA/)
  assert.match(home, /Liên kết OA IOT Generation/)
  assert.match(home, /campaign-zalo-nudge/)
  assert.match(home, /campaign-page-slide-prev/)
  assert.match(home, /campaign-page-slide-next/)
  assert.match(home, /Cần bạn xử lý/)
  assert.match(home, /Đang được xây dựng/)
  assert.match(home, /Đang vận hành/)
})
