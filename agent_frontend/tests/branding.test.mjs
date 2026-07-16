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
  const selector = await source('agent_frontend/src/components/ExperienceSelector.jsx')
  const modeSwitcher = await source('agent_frontend/src/components/ModeSwitcher.jsx')
  const topBar = await source('agent_frontend/src/components/TopBar.jsx')
  const composer = await source('agent_frontend/src/components/ChatPane/ChatComposer.jsx')
  const autopilot = await source('agent_frontend/src/components/AutopilotPanel.jsx')

  assert.match(selector, /grid gap-4 md:grid-cols-2/)
  assert.match(selector, /h-\[100dvh\] overflow-y-auto/)
  assert.match(app, /md:hidden/)
  assert.match(app, /flex-col md:flex-row/)
  assert.match(app, /role="tablist"/)
  assert.match(app, /aria-selected=/)
  assert.match(modeSwitcher, /aria-label="Chọn chế độ làm việc"/)
  assert.match(modeSwitcher, /role="tab"/)
  assert.match(modeSwitcher, /aria-selected=\{selected\}/)
  assert.match(modeSwitcher, /safe-area-inset-bottom/)
  assert.match(selector, /aria-label={`Chọn \${mode\.title}/)
  assert.match(topBar, /aria-label="Mở tài liệu kỹ thuật"/)
  assert.match(topBar, /aria-label="Bắt đầu campaign mới"/)
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

  assert.doesNotMatch(api, /VITE_AGENT_API_KEY|X-API-Key/)
  assert.doesNotMatch(dockerfile, /VITE_AGENT_API_KEY/)
  assert.match(nginx, /proxy_set_header X-API-Key "\$\{AGENT_API_KEY\}"/)
  assert.match(compose, /VITE_AGENT_URL: \/agent/)
  assert.match(compose, /127\.0\.0\.1:27017:27017/)
})

test('campaign strategy simulator is integrated into Autopilot', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const simulator = await source('agent_frontend/src/components/StrategySimulator.jsx')
  const api = await source('agent_frontend/src/api/agentApi.js')

  assert.match(panel, /<StrategySimulator/)
  assert.match(simulator, /Mô phỏng chiến lược campaign/)
  assert.match(simulator, /Độ phủ dự kiến/)
  assert.match(simulator, /CPM giả định/)
  assert.match(simulator, /Chọn phương án này/)
  assert.match(simulator, /triệu \$\{unit\}/)
  assert.match(simulator, /nghìn \$\{unit\}/)
  assert.match(api, /selectAutopilotStrategy/)
  assert.match(api, /\/strategy`/)
  assert.match(panel, /Bằng chứng vận hành/)
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
  assert.match(panel, /!briefReady \|\| !creativeSource/)
  assert.match(panel, /startAutopilot\(policy, creativeSource\)/)
  assert.match(api, /creative_source: creativeSource/)
  assert.match(api, /autopilot-start:\$\{SESSION_ID\}:\$\{creativeSource\}/)
})

test('Autopilot exposes a placement-aware bounded creative format plan', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const docs = await source('agent_frontend/public/tech-docs.html')

  assert.match(panel, /plan_creative_formats/)
  assert.match(panel, /Kế hoạch creative theo placement/)
  assert.match(panel, /formatPlan\.max_assets/)
  assert.match(panel, /formatPlan\.estimated_provider_calls/)
  assert.match(docs, /Bounded multi-format generation/)
  assert.doesNotMatch(docs, /Multi-format generation và creative variants vẫn là roadmap/)
})

test('Autopilot presents artifacts without Guided workflow controls', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const workspace = await source('agent_frontend/src/components/WorkspacePane/index.jsx')
  const topbar = await source('agent_frontend/src/components/TopBar.jsx')
  assert.match(app, /autopilotMode=\{false\}/)
  assert.match(workspace, /Điều hướng campaign artifacts/)
  assert.match(workspace, /!autopilotMode && <WorkFoot/)
  assert.doesNotMatch(topbar, /Minimax-M2\.5/)
})

test('workflow modes are sibling canvases and Autopilot survives tab switches', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  const switcher = await source('agent_frontend/src/components/ModeSwitcher.jsx')

  assert.match(app, /data-mode-canvas="guided"/)
  assert.match(app, /data-mode-canvas="autopilot"/)
  assert.match(app, /Autopilot is a sibling canvas, not a banner above the workspace/)
  assert.match(app, /experienceMode === 'autopilot' \? 'md:flex' : 'md:hidden'/)
  assert.match(app, /bootedRef\.current/)
  assert.match(panel, /sticky top-0/)
  assert.match(panel, /sticky bottom-2/)
  assert.match(switcher, /Chuyển chế độ không làm mất chat, workspace hoặc tiến độ đang chạy/)
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
  assert.match(panel, /disabled=\{loading \|\| \(retryAction && !retryReady\)\}/)
  assert.match(api, /workspace\/proposals\?session_id=/)
})

test('Autopilot hides stale review actions after a terminal run', async () => {
  const panel = await source('agent_frontend/src/components/AutopilotPanel.jsx')
  assert.match(panel, /const runTerminal = \['completed', 'cancelled', 'failed'\]\.includes\(run\?\.status\)/)
  assert.match(panel, /const waiting = runTerminal \? null/)
  assert.match(panel, /if \(!run\?\.run_id \|\| \['completed', 'cancelled', 'failed'\]\.includes\(run\.status\)\) return/)
})

test('demo fallback is labeled and cannot mutate workspace', async () => {
  const api = await source('agent_frontend/src/api/agentApi.js')
  const chat = await source('agent_frontend/src/hooks/useChat.js')
  const app = await source('agent_frontend/src/App.jsx')
  assert.match(api, /Chế độ demo dự phòng/)
  assert.match(api, /workspace_update: null/)
  assert.match(api, /fallback_mode: true/)
  assert.match(api, /brief chưa được lưu/)
  assert.match(api, /audience chưa được lưu/)
  assert.match(api, /setup chưa được lưu/)
  assert.match(api, /không thể xác minh kết quả campaign/)
  assert.match(api, /báo cáo chưa được khởi tạo/)
  assert.match(chat, /Không thể xóa dữ liệu phiên trên server/)
  assert.match(chat, /if \(!deleted\)/)
  assert.match(app, /if \(!deleted\) return/)
})
