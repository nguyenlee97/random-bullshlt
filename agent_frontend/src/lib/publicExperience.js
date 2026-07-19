const AGENT_PATH = '/agent'

export function hasAgentIntent(locationLike) {
  const pathname = locationLike?.pathname || '/'
  const params = new URLSearchParams(locationLike?.search || '')
  return pathname === AGENT_PATH
    || params.has('conversation')
    || params.has('auth')
    || params.has('auth_error')
}

export function agentEntryUrl(locationLike) {
  const params = new URLSearchParams(locationLike?.search || '')
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
