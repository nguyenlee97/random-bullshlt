const HOME_PATH = '/home'
const WORKSPACE_PATH = '/workspace'
const AGENT_PATH = '/agent'

const publicMode = mode => mode === 'autopilot' ? 'autopilot' : 'copilot'

export function agentPath(mode = 'copilot', conversationId = '') {
  const normalizedMode = publicMode(mode)
  const normalizedId = String(conversationId || '').trim()
  const modePath = normalizedMode === 'autopilot' ? `${AGENT_PATH}/autopilot` : AGENT_PATH
  if (!normalizedId) return modePath
  const historyModePath = normalizedMode === 'autopilot'
    ? `${AGENT_PATH}/autopilot`
    : `${AGENT_PATH}/copilot`
  return `${historyModePath}/history/${encodeURIComponent(normalizedId)}`
}

export function parseAppRoute(locationLike) {
  const pathname = locationLike?.pathname || '/'
  const params = new URLSearchParams(locationLike?.search || '')
  const segments = pathname.split('/').filter(Boolean)
  const legacyMode = params.get('mode')
  const queryRequiresAgent = params.has('conversation') || params.has('auth') || params.has('auth_error')
  const isAgentPath = segments[0] === 'agent'

  if (pathname === WORKSPACE_PATH && !params.has('conversation')) {
    return { surface: 'workspace', mode: '', conversationId: '' }
  }

  if (!isAgentPath && !queryRequiresAgent) {
    return { surface: 'home', mode: '', conversationId: '' }
  }

  const mode = segments[1] === 'autopilot'
    ? 'autopilot'
    : segments[1] === 'copilot'
      ? 'copilot'
      : legacyMode === 'autopilot'
        ? 'autopilot'
        : 'copilot'
  const pathConversationId = (
    (segments[1] === 'copilot' || segments[1] === 'autopilot')
    && segments[2] === 'history'
  ) ? segments[3] : ''
  const encodedConversationId = pathConversationId || params.get('conversation') || ''
  let conversationId = encodedConversationId
  try {
    conversationId = decodeURIComponent(encodedConversationId)
  } catch {
    // Keep malformed legacy IDs intact so the API can return the normal error.
  }

  return { surface: 'agent', mode, conversationId }
}

export function hasAgentIntent(locationLike) {
  return parseAppRoute(locationLike).surface !== 'home'
}

export function agentEntryMode(locationLike) {
  const route = parseAppRoute(locationLike)
  return route.surface === 'agent' && !route.conversationId ? route.mode : ''
}

export function agentConversationId(locationLike) {
  const route = parseAppRoute(locationLike)
  return route.surface === 'agent' ? route.conversationId : ''
}

export function agentEntryUrl(locationLike, requestedMode = 'copilot', conversationId = '') {
  const params = new URLSearchParams(locationLike?.search || '')
  params.delete('tour')
  params.delete('mode')
  params.delete('conversation')
  const query = params.toString()
  return `${agentPath(requestedMode, conversationId)}${query ? `?${query}` : ''}${locationLike?.hash || ''}`
}

export function authReturnTo(locationLike) {
  const params = new URLSearchParams(locationLike?.search || '')
  params.delete('auth')
  params.delete('auth_error')
  const query = params.toString()
  return `${locationLike?.pathname || AGENT_PATH}${query ? `?${query}` : ''}${locationLike?.hash || ''}`
}

export { AGENT_PATH, HOME_PATH, WORKSPACE_PATH }
