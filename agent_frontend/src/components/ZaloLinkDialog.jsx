import { useEffect, useState } from 'react'
import { CheckCircle2, Copy, ExternalLink, Loader2, RefreshCw, X } from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'
import ZaloIcon from '@/components/ZaloIcon'

const ZALO_SDK_ID = 'zalo-social-sdk'
const ZALO_SDK_SRC = 'https://sp.zalo.me/plugins/sdk.js'

function ensureZaloSdk() {
  if (window.ZaloSocialSDK) return Promise.resolve()
  const existing = document.getElementById(ZALO_SDK_ID)
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', resolve, { once: true })
      existing.addEventListener('error', reject, { once: true })
    })
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.id = ZALO_SDK_ID
    script.src = ZALO_SDK_SRC
    script.async = true
    script.onload = resolve
    script.onerror = reject
    document.head.appendChild(script)
  })
}

export default function ZaloLinkDialog({ open, onClose, onLinked }) {
  const [attempt, setAttempt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [autoCheckedAttempt, setAutoCheckedAttempt] = useState('')
  const [widgetWidth, setWidgetWidth] = useState(400)
  const [recovering, setRecovering] = useState(false)
  const [recoveryNote, setRecoveryNote] = useState('')

  const createAttempt = async () => {
    setBusy(true)
    setError('')
    setCopied(false)
    setAutoCheckedAttempt('')
    setRecoveryNote('')
    try { setAttempt(await AgentAPI.startZaloChannelLink()) }
    catch (caught) { setError(caught.message) }
    finally { setBusy(false) }
  }

  useEffect(() => {
    if (!open) {
      setAttempt(null)
      setError('')
      return
    }
    createAttempt()
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const fitWidget = () => setWidgetWidth(
      Math.min(420, Math.max(240, window.innerWidth - 80)),
    )
    fitWidget()
    window.addEventListener('resize', fitWidget)
    return () => window.removeEventListener('resize', fitWidget)
  }, [open])

  useEffect(() => {
    if (!open || !attempt?.attempt_id || attempt.status !== 'pending') return undefined
    const timer = window.setInterval(async () => {
      try {
        const current = await AgentAPI.getZaloChannelLink(attempt.attempt_id)
        setAttempt(previous => ({ ...previous, ...current }))
        if (current.status === 'linked') onLinked?.()
      } catch (caught) {
        setError(caught.message)
      }
    }, 2000)
    return () => window.clearInterval(timer)
  }, [attempt?.attempt_id, attempt?.status, onLinked, open])

  useEffect(() => {
    if (!open || !attempt?.oa_id || attempt.status !== 'pending') return undefined
    ensureZaloSdk()
      .then(() => window.ZaloSocialSDK?.reload?.())
      .catch(() => setError('Không thể tải Official Account Zalo. Bạn vẫn có thể dùng cách gửi mã bên dưới.'))
    return undefined
  }, [attempt?.attempt_id, attempt?.oa_id, attempt?.status, open, widgetWidth])

  const recoverExistingFollower = async (
    attemptId = attempt?.attempt_id,
    { announce = true } = {},
  ) => {
    if (!attemptId) return
    setRecovering(true)
    setError('')
    setRecoveryNote('')
    try {
      const result = await AgentAPI.recoverExistingZaloFollower(attemptId)
      if (result.status === 'linked') {
        setAttempt(previous => ({ ...previous, ...result }))
        onLinked?.()
        return
      }
      const notes = {
        existing_follower_not_found: 'Chưa tìm thấy tài khoản Zalo này trong danh sách đang quan tâm OA. Bạn vẫn có thể gửi mã xác minh bên dưới.',
        oa_user_api_unavailable: 'Zalo chưa cho phép kiểm tra tự động lúc này. Bạn vẫn có thể gửi mã xác minh bên dưới.',
        zalo_login_identity_not_found: 'Hãy kết nối đăng nhập Zalo trước khi kiểm tra tự động.',
        link_attempt_not_pending: 'Phiên liên kết đã hết hạn. Hãy tạo mã mới và thử lại.',
      }
      if (announce) {
        setRecoveryNote(notes[result.reason] || 'Chưa thể xác nhận tự động. Bạn vẫn có thể gửi mã xác minh bên dưới.')
      }
    } catch (caught) {
      if (announce) setRecoveryNote(caught.message)
    } finally {
      setRecovering(false)
    }
  }

  useEffect(() => {
    if (
      !open
      || !attempt?.attempt_id
      || attempt.status !== 'pending'
      || !attempt.existing_follower_check_available
      || autoCheckedAttempt === attempt.attempt_id
    ) return
    setAutoCheckedAttempt(attempt.attempt_id)
    recoverExistingFollower(attempt.attempt_id, { announce: false })
  }, [attempt?.attempt_id, attempt?.existing_follower_check_available, attempt?.status, autoCheckedAttempt, open])

  if (!open) return null
  const linked = attempt?.status === 'linked'
  const terminal = ['expired', 'superseded', 'conflict'].includes(attempt?.status)

  return (
    <div className="fixed inset-0 z-[105] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="zalo-link-title">
      <button type="button" className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Đóng" />
      <div className="relative max-h-[calc(100dvh-2rem)] w-full max-w-lg overflow-y-auto rounded-3xl border border-slate-200 bg-white p-4 shadow-2xl sm:p-6">
        <button type="button" onClick={onClose} className="absolute right-4 top-4 rounded-lg p-2 text-slate-400 hover:bg-slate-100" aria-label="Đóng"><X className="h-4 w-4" /></button>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-500">
          {linked ? <CheckCircle2 className="h-6 w-6" /> : <ZaloIcon className="h-9 w-9" />}
        </div>
        <h2 id="zalo-link-title" className="mt-4 text-xl font-black text-slate-900">Liên kết chat Zalo OA</h2>

        {linked ? (
          <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            <p className="font-bold">Đã liên kết thành công</p>
            <p className="mt-1">Tin nhắn từ tài khoản Zalo này giờ có thể được nhận diện là tài khoản Advertising Agent của bạn.</p>
          </div>
        ) : (
          <>
            <p className="mt-3 text-sm leading-6 text-slate-600">Quan tâm <strong>{attempt?.oa_name || 'IOT Generation'}</strong> để kết nối Zalo với Advertising Agent.</p>

            {attempt?.oa_id && (
              <section className="mt-4 overflow-hidden rounded-2xl border border-brand-200 bg-brand-50/60 p-3 sm:p-4" aria-label="Official Account Zalo">
                <div className="flex items-center gap-3">
                  <ZaloIcon className="h-10 w-10 shrink-0" />
                  <div>
                    <p className="text-sm font-black text-slate-900">{attempt?.oa_name || 'IOT Generation'}</p>
                    <p className="text-xs text-slate-600">Official Account trên Zalo</p>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-center overflow-hidden rounded-xl bg-white shadow-sm">
                  <div
                    key={`${attempt.attempt_id}-${widgetWidth}`}
                    className="zalo-follow-button"
                    data-oaid={attempt.oa_id}
                    data-cover="yes"
                    data-article="0"
                    data-width={`${widgetWidth}px`}
                    data-height={`${Math.max(220, Math.round(widgetWidth * 0.62))}px`}
                  />
                </div>

                {attempt?.existing_follower_check_available && (
                  <>
                    <button type="button" onClick={() => recoverExistingFollower()} disabled={recovering || busy}
                      className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-bold text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60">
                      {recovering ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      {recovering ? 'Đang kiểm tra với Zalo…' : 'Đã quan tâm · Kiểm tra và hoàn tất'}
                    </button>
                    <p className="mt-2 text-center text-[11px] leading-5 text-slate-500">Hệ thống tự kiểm tra khi cửa sổ này mở; nút trên dùng để kiểm tra lại ngay sau khi bạn bấm Quan tâm.</p>
                    {recoveryNote && <p className="mt-2 text-center text-xs leading-5 text-brand-800">{recoveryNote}</p>}
                  </>
                )}
              </section>
            )}

            <details className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <summary className="cursor-pointer font-bold">Không thể hoàn tất qua widget?</summary>
              <p className="mt-3 leading-6">Gửi tin nhắn xác minh sau cho Official Account. Đây là phương án dự phòng khi Zalo chưa đồng bộ trạng thái quan tâm.</p>
              {busy && !attempt ? (
                <Loader2 className="mx-auto mt-3 h-6 w-6 animate-spin text-brand-500" />
              ) : attempt?.link_code ? (
                <>
                  <p className="mt-3 rounded-xl bg-white px-3 py-3 text-center font-mono text-lg font-black tracking-wider text-slate-900">LINK {attempt.link_code}</p>
                  <button type="button" onClick={async () => {
                    await navigator.clipboard.writeText(`LINK ${attempt.link_code}`)
                    setCopied(true)
                  }} className="mx-auto mt-3 flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-bold text-brand-700 shadow-sm">
                    <Copy className="h-3.5 w-3.5" /> {copied ? 'Đã sao chép' : 'Sao chép mã xác minh'}
                  </button>
                  {attempt?.oa_id && <a href={`https://zalo.me/${attempt.oa_id}`} target="_blank" rel="noreferrer" className="mx-auto mt-3 flex w-fit items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-2 text-xs font-bold text-white hover:bg-brand-600"><ExternalLink className="h-3.5 w-3.5" /> Mở {attempt?.oa_name || 'IOT Generation'} trong Zalo</a>}
                </>
              ) : null}
            </details>
            {attempt?.status === 'pending' && <p className="mt-3 flex items-center justify-center gap-2 text-xs font-semibold text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Đang chờ Zalo xác nhận liên kết…</p>}
            {terminal && <button type="button" onClick={createAttempt} disabled={busy} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-bold text-white hover:bg-brand-600"><RefreshCw className="h-4 w-4" /> Tạo phiên liên kết mới</button>}
          </>
        )}
        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button type="button" onClick={onClose} className="mt-5 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-50">{linked ? 'Hoàn tất' : 'Đóng'}</button>
      </div>
    </div>
  )
}
