import { useCallback, useState } from 'react'
import { AgentAPI } from '@/api/agentApi'
import { authReturnTo } from '@/lib/publicExperience'

const anonymousState = {
  authenticated: false,
  user: null,
  anonymous_identity_present: true,
  auth_methods: { local_test: true, zalo: false, zalo_oa_link: false },
  channels: { zalo_oa: null },
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
        auth_methods: identity.auth_methods,
        channels: identity.channels,
      }
      setIdentity(current)
      return { ...result, identity: current }
    } catch (caught) {
      setError(caught.message)
      throw caught
    } finally {
      setBusy(false)
    }
  }, [identity.auth_methods, identity.channels])

  const login = useCallback(async credentials => {
    setBusy(true)
    setError('')
    try {
      const result = await AgentAPI.loginAccount(credentials)
      const current = {
        authenticated: true,
        user: result.user,
        anonymous_identity_present: true,
        auth_methods: identity.auth_methods,
        channels: identity.channels,
      }
      setIdentity(current)
      return { ...result, identity: current }
    } catch (caught) {
      setError(caught.message)
      throw caught
    } finally {
      setBusy(false)
    }
  }, [identity.auth_methods, identity.channels])

  const startZalo = useCallback(async (intent = 'login') => {
    setBusy(true)
    setError('')
    try {
      const result = await AgentAPI.startZaloAuth({
        intent,
        returnTo: authReturnTo(window.location),
      })
      window.location.assign(result.authorization_url)
      return result
    } catch (caught) {
      setError(caught.message)
      setBusy(false)
      throw caught
    }
  }, [])

  const unlinkZaloChannel = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      await AgentAPI.unlinkZaloChannel()
      return await refresh()
    } catch (caught) {
      setError(caught.message)
      throw caught
    } finally {
      setBusy(false)
    }
  }, [refresh])

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
    startZalo,
    logout,
    unlinkZaloChannel,
    clearError,
    listSessions: AgentAPI.listAccountSessions,
    revokeSession: AgentAPI.revokeAccountSession,
  }
}
