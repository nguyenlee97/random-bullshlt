import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const hook = readFileSync(new URL('../src/hooks/useIdentity.js', import.meta.url), 'utf8')
const auth = readFileSync(new URL('../src/components/AuthDialog.jsx', import.meta.url), 'utf8')
const accountMenu = readFileSync(new URL('../src/components/AccountMenu.jsx', import.meta.url), 'utf8')
const history = readFileSync(new URL('../src/components/ConversationHistory.jsx', import.meta.url), 'utf8')
const home = readFileSync(new URL('../src/components/ExperienceSelector.jsx', import.meta.url), 'utf8')

test('cookie authenticated mutations receive one centralized CSRF header', () => {
  assert.match(api, /cookieGet\('aa_csrf'\)/)
  assert.match(api, /'X-CSRF-Token': csrf/)
  assert.match(api, /\['POST', 'PUT', 'PATCH', 'DELETE'\]/)
  assert.doesNotMatch(api, /storageSet\(['"](?:aa_account|account-token|password)/)
})

test('local account API and state expose register login logout me and session revocation', () => {
  for (const method of ['getAuthMe', 'registerAccount', 'loginAccount', 'logoutAccount', 'listAccountSessions', 'revokeAccountSession']) {
    assert.match(api, new RegExp(`${method}\\(`))
  }
  assert.match(hook, /useIdentity/)
  assert.match(auth, /'new-password'/)
  assert.match(auth, /'current-password'/)
})

test('account and device histories are labeled and only device campaigns can claim', () => {
  assert.match(home, /Tài khoản/)
  assert.match(home, /Trên thiết bị/)
  assert.match(home, /item\.can_claim/)
  assert.match(history, /item\.can_claim/)
  assert.match(api, /claimConversation\(conversationId\)/)
})

test('claim updates ownership in place without recreating the active conversation', () => {
  const claimBody = app.slice(app.indexOf('const confirmClaimConversation'), app.indexOf('const startCampaign'))
  assert.match(claimBody, /AgentAPI\.claimConversation/)
  assert.match(claimBody, /ownership: 'account'/)
  assert.doesNotMatch(claimBody, /applyConversationContext|newChat|createConversation/)
  assert.match(app, /Campaign này đang được lưu trên thiết bị/)
})

test('logout drops account-owned open state while anonymous-first entry stays available', () => {
  assert.match(app, /current\?\.ownership === 'account'/)
  assert.match(app, /handleNewChat\(\)/)
  assert.match(home, /Bắt đầu campaign mới/)
  assert.match(auth, /Bạn vẫn có thể dùng ẩn danh/)
})

test('cross-device resume restores the first incomplete guided step and keeps the compact account control accessible', () => {
  const restoreBody = app.slice(app.indexOf('const applyConversationContext'), app.indexOf('const handleReset'))
  assert.match(restoreBody, /deriveStepStatuses\(STEPS\.map\(\(\) => 'pending'\), context\.workspace\)/)
  assert.match(restoreBody, /setCurrentStep\(firstIncomplete/)
  assert.match(accountMenu, /aria-label={`Tài khoản/)
})
