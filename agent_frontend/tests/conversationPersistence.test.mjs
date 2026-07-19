import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const history = readFileSync(new URL('../src/components/ConversationHistory.jsx', import.meta.url), 'utf8')
const homepage = readFileSync(new URL('../src/components/ExperienceSelector.jsx', import.meta.url), 'utf8')
const deleteDialog = readFileSync(new URL('../src/components/DeleteConversationDialog.jsx', import.meta.url), 'utf8')

test('anonymous device credential uses an HttpOnly cookie with legacy migration only', () => {
  assert.match(api, /anonymous-token/)
  assert.match(api, /X-Anonymous-Token/)
  assert.match(api, /credentials: 'include'/)
  assert.match(api, /storageSet\('anonymous-token', ''\)/)
  assert.match(api, /initializeIdentity/)
})

test('campaign resume hydrates transcript, workspace, pending proposals and autopilot run', () => {
  assert.match(api, /pending_proposals/)
  assert.match(app, /hydrateMessages\(context\.ui_messages/)
  assert.match(app, /hydrateCanonicalWorkspace\(context\.workspace\)/)
  assert.match(app, /initialRun=\{restoredAutopilotRun\}/)
  assert.match(app, /context\.experience_mode \|\| context\.workspace\?\.experience_mode/)
  assert.match(app, /setAudienceRecommendation\(null\)/)
  assert.match(app, /campaignEpochRef\.current \+= 1/)
  assert.match(app, /requestConversationId !== currentConversationIdRef\.current/)
  assert.match(app, /!canonicalAudience\?\.attrs\?\.length/)
})

test('fresh loads stay on the homepage until a campaign is explicitly opened', () => {
  assert.match(app, /initializeIdentity\(\{ restoreCurrent: false \}\)/)
  assert.match(app, /setConversationHistory\(await AgentAPI\.listConversations\(\)\)/)
  assert.match(homepage, /Bạn muốn Agent/)
  assert.match(homepage, /đồng hành thế nào/)
  assert.match(homepage, /Tiếp nối những campaign đang viết dở/)
  assert.match(homepage, /Campaign Copilot/)
  assert.doesNotMatch(homepage, /Quy trình từng bước/)
})

test('history UI exposes resume, archive and new campaign actions', () => {
  assert.match(history, /Lịch sử chiến dịch/)
  assert.match(history, /onResume/)
  assert.match(history, /onArchive/)
  assert.match(history, /onNew/)
  assert.match(history, /latest_run_summary/)
  assert.match(history, /Tiến độ Autopilot/)
  assert.match(homepage, /latest_run_summary/)
  assert.match(homepage, /Tiến độ Autopilot/)
  assert.match(app, /if \(!identityReady \|\| \(experienceMode && !historyOpen\)\) return undefined/)
  assert.match(app, /setInterval\(refresh, 4000\)/)
})

test('conversation deletion is available individually and in bulk with safety confirmation', () => {
  assert.match(api, /deleteConversation\(conversationId\)/)
  assert.match(api, /deleteAllConversations\(\)/)
  assert.match(api, /confirmation: 'DELETE_ALL'/)
  assert.match(homepage, /Xóa tất cả/)
  assert.match(history, /Xóa toàn bộ lịch sử/)
  assert.match(deleteDialog, /role="alertdialog"/)
  assert.match(deleteDialog, /XÓA TẤT CẢ/)
  assert.match(deleteDialog, /Thao tác này không thể hoàn tác/)
})
