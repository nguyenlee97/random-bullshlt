const HOME_PATH = '/home'
const MANAGE_PATH = '/manage'
const LEGACY_WORKSPACE_PATH = '/workspace'
const AGENT_PATH = '/agent'
const CAMPAIGN_MANAGE_PREFIX = `${MANAGE_PATH}/campaigns`

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

export function campaignManagePath(campaignId = '') {
  const normalizedId = String(campaignId || '').trim()
  return normalizedId
    ? `${CAMPAIGN_MANAGE_PREFIX}/${encodeURIComponent(normalizedId)}`
    : MANAGE_PATH
}

export function parseAppRoute(locationLike) {
  const pathname = locationLike?.pathname || '/'
  const params = new URLSearchParams(locationLike?.search || '')
  const segments = pathname.split('/').filter(Boolean)
  const legacyMode = params.get('mode')
  const queryRequiresAgent = params.has('conversation') || params.has('auth') || params.has('auth_error')
  const isAgentPath = segments[0] === 'agent'

  if (segments[0] === 'manage' && segments[1] === 'campaigns' && segments[2]) {
    let campaignId = segments[2]
    try { campaignId = decodeURIComponent(campaignId) } catch { /* API handles malformed IDs */ }
    return { surface: 'campaign', mode: '', conversationId: '', campaignId }
  }

  if (
    (pathname === MANAGE_PATH || pathname === LEGACY_WORKSPACE_PATH)
    && !params.has('conversation')
  ) {
    return { surface: 'manage', mode: '', conversationId: '' }
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

  return {
    surface: 'agent',
    mode,
    conversationId,
    readOnly: params.get('readonly') === '1',
  }
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
  params.delete('readonly')
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

export { AGENT_PATH, CAMPAIGN_MANAGE_PREFIX, HOME_PATH, MANAGE_PATH }
