import { useCallback, useState } from 'react'
import { AgentAPI } from '@/api/agentApi'

const anonymousState = {
  authenticated: false,
  user: null,
  anonymous_identity_present: true,
}

export function useIdentity() {
  const [identity, setIdentity] = useState(anonymousState)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    const current = await AgentAPI.getAuthMe()
    setIdentity(current)
    return current
  }, [])

  const register = useCallback(async credentials => {
    setBusy(true)
    setError('')
    try {
      const result = await AgentAPI.registerAccount(credentials)
      const current = {
        authenticated: true,
        user: result.user,
        anonymous_identity_present: true,
      }
      setIdentity(current)
      return { ...result, identity: current }
    } catch (caught) {
      setError(caught.message)
      throw caught
    } finally {
      setBusy(false)
    }
  }, [])

  const login = useCallback(async credentials => {
    setBusy(true)
    setError('')
    try {
      const result = await AgentAPI.loginAccount(credentials)
      const current = {
        authenticated: true,
        user: result.user,
        anonymous_identity_present: true,
      }
      setIdentity(current)
      return { ...result, identity: current }
    } catch (caught) {
      setError(caught.message)
      throw caught
    } finally {
      setBusy(false)
    }
  }, [])

  const logout = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      await AgentAPI.logoutAccount()
      const current = await AgentAPI.getAuthMe()
      setIdentity(current)
      return current
    } catch (caught) {
      setError(caught.message)
      throw caught
    } finally {
      setBusy(false)
    }
  }, [])

  const clearError = useCallback(() => setError(''), [])

  return {
    identity,
    authenticated: identity.authenticated,
    user: identity.user,
    busy,
    error,
    refresh,
    register,
    login,
    logout,
    clearError,
    listSessions: AgentAPI.listAccountSessions,
    revokeSession: AgentAPI.revokeAccountSession,
  }
}
