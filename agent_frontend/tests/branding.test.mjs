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
  const topBar = await source('agent_frontend/src/components/TopBar.jsx')
  const composer = await source('agent_frontend/src/components/ChatPane/ChatComposer.jsx')
  const autopilot = await source('agent_frontend/src/components/AutopilotPanel.jsx')

  assert.match(selector, /grid gap-4 md:grid-cols-2/)
  assert.match(app, /md:hidden/)
  assert.match(app, /flex-col md:flex-row/)
  assert.match(app, /role="tablist"/)
  assert.match(app, /aria-selected=/)
  assert.match(selector, /aria-label={`Chọn \${mode\.title}/)
  assert.match(topBar, /aria-label="Mở tài liệu kỹ thuật"/)
  assert.match(topBar, /aria-label="Bắt đầu campaign mới"/)
  assert.match(composer, /aria-label="Tin nhắn gửi Advertising Agent"/)
  assert.match(composer, /aria-label=\{busy \? 'Advertising Agent đang xử lý' : 'Gửi tin nhắn'\}/)
  assert.match(autopilot, /aria-label="Tạm dừng Autopilot"/)
  assert.match(autopilot, /aria-label="Hủy Autopilot run"/)
})
