import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { ongoingAutopilotConversations } from '../src/lib/conversationDeletion.js'
import { partitionConversationHistory } from '../src/lib/conversationHistory.js'

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
  assert.match(app, /setConversationHistory\(await AgentAPI\.listConversations\(true\)\)/)
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

test('archived campaigns remain discoverable in management and workspace history', () => {
  const conversations = [
    { conversation_id: 'active', archived_at: null },
    { conversation_id: 'archived', archived_at: '2026-07-29T10:00:00Z' },
  ]
  const partitioned = partitionConversationHistory(conversations)

  assert.deepEqual(partitioned.active.map(item => item.conversation_id), ['active'])
  assert.deepEqual(partitioned.archived.map(item => item.conversation_id), ['archived'])
  assert.match(app, /AgentAPI\.listConversations\(true\)/)
  assert.match(app, /archived_at: new Date\(\)\.toISOString\(\)/)
  for (const surface of [homepage, history]) {
    assert.match(surface, /Đang hoạt động/)
    assert.match(surface, /Đã lưu trữ/)
    assert.match(surface, /partitionConversationHistory/)
  }
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

test('bulk deletion warns before deleting conversations with ongoing Autopilot runs', () => {
  const conversations = [
    { conversation_id: 'queued', latest_run_summary: { status: 'queued' } },
    { conversation_id: 'review', latest_run_summary: { status: 'waiting_review' } },
    { conversation_id: 'paused', latest_run_summary: { status: 'paused' } },
    { conversation_id: 'done', latest_run_summary: { status: 'completed' } },
    { conversation_id: 'failed', latest_run_summary: { status: 'failed' } },
    { conversation_id: 'cancelled', latest_run_summary: { status: 'cancelled' } },
    { conversation_id: 'copilot' },
  ]

  assert.deepEqual(
    ongoingAutopilotConversations(conversations).map(item => item.conversation_id),
    ['queued', 'review', 'paused'],
  )
  assert.match(app, /AgentAPI\.listConversations\(true\)/)
  assert.match(app, /type: 'autopilot-active'/)
  assert.match(deleteDialog, /Chưa thể xóa toàn bộ lịch sử/)
  assert.match(deleteDialog, /Không có cuộc trò chuyện nào bị xóa/)
})

test('deleting the active conversation returns to management without creating a replacement chat', () => {
  const managerBody = app.slice(
    app.indexOf('const returnToCampaignManager'),
    app.indexOf('const handleNewChat'),
  )
  const deleteBody = app.slice(
    app.indexOf('const confirmDeleteConversations'),
    app.indexOf('// Listen for agent:reset'),
  )
  assert.match(managerBody, /clearActiveConversation\(\)/)
  assert.match(managerBody, /setPendingEntryMode\(''\)/)
  assert.match(managerBody, /MANAGE_PATH/)
  assert.doesNotMatch(managerBody, /newChat\(|agentPath\(/)
  assert.match(deleteBody, /returnToCampaignManager\('replace'\)/)
  assert.doesNotMatch(deleteBody, /handleNewChat\(\)|newChat\(/)
})
