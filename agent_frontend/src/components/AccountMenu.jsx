import { useState } from 'react'
import { ChevronDown, Laptop, Loader2, LogIn, LogOut, ShieldCheck, Unlink, UserRound } from 'lucide-react'
import ZaloIcon from '@/components/ZaloIcon'

const formatTime = value => {
  if (!value) return ''
  try { return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) }
  catch { return String(value) }
}

export default function AccountMenu({
  identity,
  busy,
  onLogin,
  onLogout,
  onLoadSessions,
  onRevokeSession,
  onLinkZalo,
  onOpenZaloOA,
  onUnlinkZaloOA,
  compact = false,
}) {
  const [open, setOpen] = useState(false)
  const [sessions, setSessions] = useState(null)
  const [sessionError, setSessionError] = useState('')
  const [sessionBusy, setSessionBusy] = useState(false)
  const providers = identity?.user?.providers || []
  const hasZaloLogin = providers.includes('zalo')
  const zaloOA = identity?.channels?.zalo_oa

  if (!identity?.authenticated) {
    return (
      <button type="button" onClick={onLogin} className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-white px-3 py-2 text-xs font-bold text-brand-700 shadow-sm hover:bg-brand-50">
        <LogIn className="h-3.5 w-3.5" /> Đăng nhập
      </button>
    )
  }

  const loadSessions = async () => {
    setSessionBusy(true)
    setSessionError('')
    try { setSessions(await onLoadSessions()) }
    catch (error) { setSessionError(error.message) }
    finally { setSessionBusy(false) }
  }

  const revoke = async sessionId => {
    setSessionBusy(true)
    setSessionError('')
    try {
      await onRevokeSession(sessionId)
      setSessions(items => (items || []).filter(item => item.session_id !== sessionId))
    } catch (error) { setSessionError(error.message) }
    finally { setSessionBusy(false) }
  }

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(value => !value)} className="inline-flex max-w-[190px] items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50" aria-expanded={open} aria-label={`Tài khoản ${identity.user?.display_name || ''}`.trim()}>
        <span className="flex h-6 w-6 shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-100 text-brand-700">
          {identity.user?.avatar_url ? <img src={identity.user.avatar_url} alt="" className="h-full w-full object-cover" referrerPolicy="no-referrer" /> : <UserRound className="h-3.5 w-3.5" />}
        </span>
        {!compact && <span className="truncate">{identity.user?.display_name}</span>}
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-[90] mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white p-3 shadow-2xl">
          <div className="rounded-xl bg-slate-50 p-3">
            <p className="font-bold text-slate-900">{identity.user?.display_name}</p>
            <p className="mt-0.5 truncate text-xs text-slate-500">{identity.user?.email || (hasZaloLogin ? 'Đăng nhập bằng Zalo' : 'Tài khoản kiểm thử')}</p>
            <p className="mt-2 flex items-center gap-1 text-[11px] font-semibold text-emerald-700"><ShieldCheck className="h-3 w-3" /> {hasZaloLogin ? 'Zalo đã xác thực' : (identity.user?.email_verified ? 'Email đã xác minh' : 'Email chưa xác minh')}</p>
          </div>

          {!hasZaloLogin && identity.auth_methods?.zalo && (
            <button type="button" onClick={onLinkZalo} disabled={busy} className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-bold text-[#0068ff] hover:bg-blue-50">
              <ZaloIcon className="h-5 w-5" /> Kết nối đăng nhập Zalo
            </button>
          )}
          {hasZaloLogin && identity.auth_methods?.zalo_oa_link && !zaloOA && (
            <button type="button" onClick={onOpenZaloOA} disabled={busy} className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-bold text-[#0068ff] hover:bg-blue-50">
              <ZaloIcon className="h-5 w-5" /> Liên kết chat Zalo OA
            </button>
          )}
          {zaloOA && (
            <button type="button" onClick={onUnlinkZaloOA} disabled={busy} className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-bold text-slate-600 hover:bg-slate-50">
              <Unlink className="h-3.5 w-3.5" /> Hủy liên kết Zalo OA
            </button>
          )}

          <button type="button" onClick={() => sessions ? setSessions(null) : loadSessions()} disabled={sessionBusy}
            className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-bold text-slate-600 hover:bg-slate-50">
            {sessionBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Laptop className="h-3.5 w-3.5" />}
            {sessions ? 'Ẩn phiên đăng nhập' : 'Quản lý phiên đăng nhập'}
          </button>
          {sessions && (
            <div className="max-h-48 space-y-2 overflow-y-auto px-1 py-2">
              {sessions.map(session => (
                <div key={session.session_id} className="rounded-lg border border-slate-200 p-2 text-[11px] text-slate-500">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-bold text-slate-700">{session.current ? 'Thiết bị này' : (session.user_agent_label || 'Thiết bị khác')}</p>
                      <p>{formatTime(session.last_seen_at)}</p>
                    </div>
                    {!session.current && <button type="button" onClick={() => revoke(session.session_id)} className="font-bold text-red-600 hover:text-red-700">Thu hồi</button>}
                  </div>
                </div>
              ))}
            </div>
          )}
          {sessionError && <p className="px-3 py-1 text-xs text-red-600">{sessionError}</p>}
          <button type="button" onClick={onLogout} disabled={busy} className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-bold text-red-600 hover:bg-red-50">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <LogOut className="h-3.5 w-3.5" />} Đăng xuất
          </button>
        </div>
      )}
    </div>
  )
}
