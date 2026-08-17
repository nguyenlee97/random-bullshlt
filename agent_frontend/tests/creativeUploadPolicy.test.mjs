import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  creativeUploadIdempotencyKey,
  OPENAI_CREATIVE_UPLOAD_MAX_ATTEMPTS,
  OPENAI_CREATIVE_UPLOAD_TIMEOUT_MS,
  shouldRetryCreativeUpload,
} from '../src/lib/creativeUploadPolicy.js'

test('OpenAI creative upload keys are stable and conversation scoped', () => {
  const input = {
    conversationId: 'conv-123',
    sessionId: 'sess-ignored',
    file: { id: 'demo-zplay-znews-top-banner', size: 1833769 },
    index: 4,
  }
  assert.equal(creativeUploadIdempotencyKey(input), creativeUploadIdempotencyKey(input))
  assert.notEqual(
    creativeUploadIdempotencyKey(input),
    creativeUploadIdempotencyKey({ ...input, conversationId: 'conv-456' }),
  )
})

test('OpenAI creative uploads retry only transient failures', () => {
  assert.equal(OPENAI_CREATIVE_UPLOAD_TIMEOUT_MS, 90000)
  assert.equal(OPENAI_CREATIVE_UPLOAD_MAX_ATTEMPTS, 2)
  assert.equal(shouldRetryCreativeUpload({ attempt: 1, status: 0 }), true)
  assert.equal(shouldRetryCreativeUpload({ attempt: 1, status: 429 }), true)
  assert.equal(shouldRetryCreativeUpload({ attempt: 1, status: 503 }), true)
  assert.equal(shouldRetryCreativeUpload({ attempt: 1, status: 400 }), false)
  assert.equal(shouldRetryCreativeUpload({ attempt: 2, status: 503 }), false)
})

test('OpenAI resilient upload is provider scoped and sends an idempotency key', () => {
  const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
  const chat = readFileSync(new URL('../src/hooks/useChat.js', import.meta.url), 'utf8')
  const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')

  assert.match(api, /'X-Idempotency-Key': idempotencyKey/)
  assert.match(api, /resilientUpload/)
  assert.match(chat, /\{ resilientUpload: openaiCampaignFlow \}/)
  assert.match(app, /openaiCampaignFlow: currentConversationModel === 'openai_gpt_5_4_mini'/)
})
