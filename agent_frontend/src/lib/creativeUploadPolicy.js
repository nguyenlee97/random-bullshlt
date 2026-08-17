export const OPENAI_CREATIVE_UPLOAD_TIMEOUT_MS = 90000
export const OPENAI_CREATIVE_UPLOAD_MAX_ATTEMPTS = 2

const safeKeyPart = value => String(value || '')
  .replace(/[^a-zA-Z0-9:_-]+/g, '-')
  .replace(/^-+|-+$/g, '')
  .slice(0, 120)

export function creativeUploadIdempotencyKey({
  conversationId,
  sessionId,
  file,
  index = 0,
}) {
  const scope = safeKeyPart(conversationId || sessionId || 'anonymous')
  const identity = safeKeyPart(file?.id || file?.name || `file-${index}`)
  const size = Number(file?.size || 0)
  return `openai-creative:${scope}:${identity}:${size}`
}

export function shouldRetryCreativeUpload({
  attempt,
  maxAttempts = OPENAI_CREATIVE_UPLOAD_MAX_ATTEMPTS,
  status = 0,
}) {
  if (attempt >= maxAttempts) return false
  if (!status) return true
  return status === 408 || status === 425 || status === 429 || status >= 500
}
