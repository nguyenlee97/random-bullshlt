const AGENT_PATH = '/agent'

export function hasAgentIntent(locationLike) {
  const pathname = locationLike?.pathname || '/'
  const params = new URLSearchParams(locationLike?.search || '')
  return pathname === AGENT_PATH
    || params.has('conversation')
    || params.has('auth')
    || params.has('auth_error')
}

export function agentEntryMode(locationLike) {
  const mode = new URLSearchParams(locationLike?.search || '').get('mode')
  return mode === 'copilot' || mode === 'autopilot' ? mode : ''
}

export function agentEntryUrl(locationLike, requestedMode = '') {
  const params = new URLSearchParams(locationLike?.search || '')
  params.delete('tour')
  if (requestedMode === 'copilot' || requestedMode === 'autopilot') {
    params.set('mode', requestedMode)
  } else if (!agentEntryMode(locationLike)) {
    params.delete('mode')
  }
  const query = params.toString()
  return `${AGENT_PATH}${query ? `?${query}` : ''}${locationLike?.hash || ''}`
}

export function authReturnTo(locationLike) {
  const params = new URLSearchParams(locationLike?.search || '')
  params.delete('auth')
  params.delete('auth_error')
  const query = params.toString()
  return `${locationLike?.pathname || AGENT_PATH}${query ? `?${query}` : ''}${locationLike?.hash || ''}`
}

export { AGENT_PATH }
