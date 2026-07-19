import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const hook = readFileSync(new URL('../src/hooks/useIdentity.js', import.meta.url), 'utf8')
const auth = readFileSync(new URL('../src/components/AuthDialog.jsx', import.meta.url), 'utf8')
const zaloIcon = readFileSync(new URL('../src/components/ZaloIcon.jsx', import.meta.url), 'utf8')
const accountMenu = readFileSync(new URL('../src/components/AccountMenu.jsx', import.meta.url), 'utf8')
const zaloLink = readFileSync(new URL('../src/components/ZaloLinkDialog.jsx', import.meta.url), 'utf8')
const history = readFileSync(new URL('../src/components/ConversationHistory.jsx', import.meta.url), 'utf8')
const home = readFileSync(new URL('../src/components/ExperienceSelector.jsx', import.meta.url), 'utf8')

test('cookie authenticated mutations receive one centralized CSRF header', () => {
  assert.match(api, /cookieGet\('aa_csrf'\)/)
  assert.match(api, /'X-CSRF-Token': csrf/)
  assert.match(api, /\['POST', 'PUT', 'PATCH', 'DELETE'\]/)
  assert.match(api, /response\.clone\(\)\.json/)
  assert.match(api, /failure\?\.error !== 'csrf_failed'/)
  assert.match(api, /response = await send\(\)/)
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

test('Zalo is the primary login while local auth remains an explicit test fallback', () => {
  for (const method of ['startZaloAuth', 'startZaloChannelLink', 'getZaloChannelLink', 'unlinkZaloChannel']) {
    assert.match(api, new RegExp(`${method}\\(`))
  }
  assert.match(auth, /Tiếp tục với Zalo/)
  assert.match(auth, /<ZaloIcon/)
  assert.match(zaloIcon, />\s*Zalo\s*</)
  assert.match(zaloIcon, /#0068ff/)
  assert.match(auth, /email dành cho kiểm thử/)
  assert.match(hook, /account\.startZalo|AgentAPI\.startZaloAuth|startZalo/)
  assert.match(accountMenu, /Kết nối đăng nhập Zalo/)
  assert.match(accountMenu, /Liên kết chat Zalo OA/)
  assert.match(zaloLink, /LINK \$\{attempt\.link_code\}/)
  assert.match(zaloLink, /getZaloChannelLink/)
  assert.match(zaloLink, /zalo-follow-button/)
  assert.match(zaloLink, /data-oaid/)
  assert.match(zaloLink, /data-width=\{`\$\{widgetWidth\}px`\}/)
  assert.match(zaloLink, /data-height=/)
  assert.match(zaloLink, /widgetWidth \* 0\.62/)
  assert.match(zaloLink, /data-cover="yes"/)
  assert.match(zaloLink, /data-article="0"/)
  assert.match(zaloLink, /ZaloSocialSDK\?\.reload/)
  assert.match(zaloLink, /Đã quan tâm · Kiểm tra và hoàn tất/)
  assert.match(zaloLink, /Đang chờ Zalo xác nhận liên kết/)
  assert.match(api, /recoverExistingZaloFollower/)
  assert.match(zaloLink, /autoCheckedAttempt/)
  assert.match(zaloLink, /announce: false/)
  assert.match(zaloLink, /existing_follower_check_available/)
  assert.match(zaloLink, /IOT Generation/)
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
  assert.match(home, /Bạn muốn Agent/)
  assert.match(home, /đồng hành thế nào/)
  assert.match(auth, /Bạn vẫn có thể dùng ẩn danh/)
})

test('cross-device resume restores server-derived guided progress and keeps the compact account control accessible', () => {
  const restoreBody = app.slice(app.indexOf('const applyConversationContext'), app.indexOf('const handleReset'))
  assert.match(restoreBody, /context\.workflow_progress/)
  assert.match(restoreBody, /deriveResumeStep\(restoredStatuses, progress\)/)
  assert.match(restoreBody, /reportEntryFiredRef\.current = progress\.report_started/)
  assert.match(accountMenu, /aria-label={`Tài khoản/)
})
