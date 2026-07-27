const REDACTED_KEY = /(?:authorization|cookie|token|secret|password|api[_-]?key|csrf)/i
const BINARY_KEY = /(?:imageb64|dataurl|base64|binary|filedata)/i
const BACKEND_LOG_URL = /\/api\/agent\/logs\//

export function safeDebugValue(value, key = '', depth = 0, seen = new WeakSet()) {
  if (REDACTED_KEY.test(key)) return '[redacted]'
  if (BINARY_KEY.test(key) && typeof value === 'string') {
    return `[omitted binary payload: ${value.length} chars]`
  }
  if (typeof value === 'string') {
    if (/^data:(?:image|video|audio)\//i.test(value)) {
      return `[omitted data URL: ${value.length} chars]`
    }
    return value.length > 12000 ? `${value.slice(0, 12000)}…[truncated ${value.length - 12000} chars]` : value
  }
  if (value == null || typeof value !== 'object') return value
  if (depth >= 8) return '[depth limit]'
  if (seen.has(value)) return '[circular]'
  seen.add(value)
  if (Array.isArray(value)) {
    const items = value.slice(0, 200).map(item => safeDebugValue(item, key, depth + 1, seen))
    if (value.length > 200) items.push(`[${value.length - 200} more items]`)
    return items
  }
  return Object.fromEntries(
    Object.entries(value).map(([childKey, childValue]) => [
      childKey,
      safeDebugValue(childValue, childKey, depth + 1, seen),
    ]),
  )
}

export function requestBodySnapshot(body) {
  if (body == null) return null
  if (typeof body !== 'string') return safeDebugValue(String(body))
  try {
    return safeDebugValue(JSON.parse(body))
  } catch {
    return safeDebugValue(body)
  }
}

function responseFingerprint(entry) {
  return JSON.stringify([
    entry.method,
    entry.url,
    entry.status,
    entry.req_body ?? null,
    entry.res_preview ?? null,
    entry.error ?? null,
  ])
}

/**
 * Collapse unchanged GET responses even when several polling endpoints are
 * interleaved. A non-GET request starts a new phase so the export still shows
 * state before and after every user/server action. Changed responses are kept.
 */
export function compactNetworkLog(entries = []) {
  const compacted = []
  let phaseGetEntries = new Map()

  for (const entry of entries) {
    const current = safeDebugValue(entry)

    // This response is already exported in full as backend_logs.
    if (BACKEND_LOG_URL.test(current.url || '')) continue

    if (String(current.method || 'GET').toUpperCase() !== 'GET') {
      phaseGetEntries = new Map()
      compacted.push(current)
      continue
    }

    const key = responseFingerprint(current)
    const previous = phaseGetEntries.get(key)
    if (previous) {
      previous.repeat_count += 1
      previous.last_ts = current.ts
      previous.duration_ms_min = Math.min(previous.duration_ms_min, current.duration_ms || 0)
      previous.duration_ms_max = Math.max(previous.duration_ms_max, current.duration_ms || 0)
      continue
    }

    const record = {
      ...current,
      repeat_count: 1,
      last_ts: current.ts,
      duration_ms_min: current.duration_ms || 0,
      duration_ms_max: current.duration_ms || 0,
    }
    compacted.push(record)
    phaseGetEntries.set(key, record)
  }

  return compacted
}
