import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const pane = readFileSync(new URL('../src/components/WorkspacePane/index.jsx', import.meta.url), 'utf8')
const creative = readFileSync(new URL('../src/steps/CreativeStep.jsx', import.meta.url), 'utf8')
const generator = readFileSync(new URL('../src/steps/creative/AdImageGenerator.jsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const chatPane = readFileSync(new URL('../src/components/ChatPane/index.jsx', import.meta.url), 'utf8')
const debugExport = readFileSync(new URL('../src/lib/debugExport.js', import.meta.url), 'utf8')
const audience = readFileSync(new URL('../src/steps/AudienceStep.jsx', import.meta.url), 'utf8')
const autopilot = readFileSync(new URL('../src/components/AutopilotPanel.jsx', import.meta.url), 'utf8')
const autopilotReview = readFileSync(new URL('../src/components/AutopilotReview.jsx', import.meta.url), 'utf8')
const briefStep = readFileSync(new URL('../src/steps/BriefStep.jsx', import.meta.url), 'utf8')
const router = readFileSync(new URL('../../agent/router.py', import.meta.url), 'utf8')

test('OpenAI image generation carries audience context without changing GreenNode calls', () => {
  assert.match(app, /openaiCampaignFlow=\{currentConversationModel === 'openai_gpt_5_4_mini'\}/)
  assert.match(pane, /openaiCampaignFlow=\{openaiCampaignFlow\}/)
  assert.match(creative, /openaiCampaignFlow=\{openaiCampaignFlow\}/)
  assert.match(generator, /campaignFlow: openaiCampaignFlow \? 'openai' : ''/)
  assert.match(generator, /audienceContext: openaiCampaignFlow \? segment : \{\}/)
  assert.match(api, /campaign_flow: options\.campaignFlow \|\| ''/)
  assert.match(api, /audience_context: options\.audienceContext \|\| \{\}/)
  assert.match(router, /model_lock\["conversation_model"\] == OPENAI_GPT_5_4_MINI/)
  assert.match(router, /if use_openai_context:/)
})

test('OpenAI cropped images become Creative drafts before step navigation', () => {
  assert.match(
    generator,
    /if \(openaiCampaignFlow\) \{[\s\S]*?onAddToCreative\(\[newImg\]\)/,
  )
  assert.match(creative, /filter\(img => !existing\.some\(f => f\.id === img\.id\)\)/)
  assert.match(creative, /files: \[\.\.\.existing, \.\.\.toAdd\], uploaded: true/)
})

test('OpenAI Brief cannot be marked complete by a nested or incomplete patch', () => {
  assert.match(
    app,
    /currentConversationModel === 'openai_gpt_5_4_mini'[\s\S]*?target\.step === 0[\s\S]*?!isBriefReady\(formState\.brief\)[\s\S]*?originalField !== 'brief' \|\| !isBriefReady\(patchValue\)/,
  )
  assert.match(app, /rejectWorkspaceProposal\([\s\S]*?'invalid_partial_openai_brief'/)
  assert.match(briefStep, /Number\(data\.budget\) > 0 \? `\$\{data\.budget\} triệu` : '—'/)
})

test('export log keeps structured evidence but omits binary and secret values', () => {
  assert.match(chatPane, /export_schema_version: 3/)
  assert.match(chatPane, /blocks: safeDebugValue\(m\.blocks \|\| \[\]\)/)
  assert.match(chatPane, /backend_logs: backendLogs/)
  assert.match(chatPane, /ui_state: safeDebugValue\(debugContext\)/)
  assert.match(chatPane, /network_entries_captured: rawNetworkLog\.length/)
  assert.match(chatPane, /compactNetworkLog\(rawNetworkLog\)/)
  assert.match(debugExport, /omitted binary payload/)
  assert.match(debugExport, /REDACTED_KEY/)
  assert.match(api, /async getDebugLogs\(limit = 500\)/)
})

test('OpenAI audience keeps every selected segment visible above the full catalog', () => {
  assert.match(pane, /openaiCampaignFlow=\{openaiCampaignFlow\}/)
  assert.match(audience, /openaiCampaignFlow && data\.attrs\.length > 0/)
  assert.match(audience, /data-demo="selected-audience-shelf"/)
  assert.match(audience, /onClick=\{\(\) => toggleAttr\(attr\)\}/)
  assert.match(audience, /Bỏ chọn \$\{attr\.name\}/)
})

test('OpenAI audience separates direct recommendations from optional expansion', () => {
  assert.match(audience, /directReco/)
  assert.match(audience, /adjacentReco/)
  assert.match(audience, /Liên quan để mở rộng · chưa chọn/)
  assert.match(autopilotReview, /Đề xuất trực tiếp/)
  assert.match(autopilotReview, /Liên quan để mở rộng/)
  assert.match(autopilot, /!audienceReviewReady/)
  assert.doesNotMatch(autopilotReview, /Catalog không bị cắt/)
  assert.doesNotMatch(autopilot, /Catalog có \$\{audienceCatalogCount\} segment/)
})

test('Audience review exposes a real rerun action in Copilot and Autopilot', () => {
  assert.match(api, /async rerunAutopilotAudience\(runId, taskId, reason = ''\)/)
  assert.match(api, /tasks\/\$\{encodeURIComponent\(taskId\)\}\/rerun/)
  assert.match(autopilot, /waiting\.key === 'retrieve_audience'/)
  assert.match(autopilot, />\s*Gợi ý lại audience\s*</)
  assert.match(app, /nhắn “Gợi ý lại audience”/)
})

test('Copilot does not mount the hidden Autopilot poller', () => {
  assert.match(app, /experienceMode === 'autopilot' && \(\s*<AutopilotPanel/)
  assert.match(autopilot, /setInterval\(loadPrerequisites, 3000\)/)
})

test('Autopilot creative assignment uses canonical review status', () => {
  assert.match(autopilotReview, /file\.analysisStatus \|\| file\.intel\?\.effective_status/)
  assert.match(autopilotReview, /generationAdvisories/)
  assert.doesNotMatch(autopilotReview, /generationRejected/)
  assert.doesNotMatch(autopilotReview, /generationVerdict\.acceptable === false/)
})

test('anonymous identity bootstrap is shared across history refreshes', () => {
  assert.match(api, /let IDENTITY_BOOTSTRAP_PROMISE = null/)
  assert.match(api, /if \(IDENTITY_BOOTSTRAP_RESULT\) return IDENTITY_BOOTSTRAP_RESULT/)
  assert.match(api, /if \(IDENTITY_BOOTSTRAP_PROMISE\) return IDENTITY_BOOTSTRAP_PROMISE/)
})
