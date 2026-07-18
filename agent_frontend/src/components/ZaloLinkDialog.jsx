import { useEffect, useState } from 'react'
import { CheckCircle2, Copy, Loader2, MessageCircle, RefreshCw, X } from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'

const ZALO_SDK_ID = 'zalo-social-sdk'
const ZALO_SDK_SRC = 'https://sp.zalo.me/plugins/sdk.js'
const ZALO_FOLLOW_CALLBACK = 'advertisingAgentZaloFollow'

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
  const [followTouched, setFollowTouched] = useState(false)

  const createAttempt = async () => {
    setBusy(true)
    setError('')
    setCopied(false)
    setFollowTouched(false)
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
    const followCallback = async () => {
      // This browser callback is UX-only. The server links solely from the
      // signed OA follow webhook and never accepts a browser-provided user ID.
      setFollowTouched(true)
      try {
        const current = await AgentAPI.getZaloChannelLink(attempt.attempt_id)
        setAttempt(previous => ({ ...previous, ...current }))
        if (current.status === 'linked') onLinked?.()
      } catch (_) {
        // Polling remains authoritative if the provider callback races webhook delivery.
      }
    }
    window[ZALO_FOLLOW_CALLBACK] = followCallback
    ensureZaloSdk()
      .then(() => window.ZaloSocialSDK?.reload?.())
      .catch(() => setError('Không thể tải nút Quan tâm Zalo. Bạn vẫn có thể dùng cách gửi mã bên dưới.'))
    return () => {
      if (window[ZALO_FOLLOW_CALLBACK] === followCallback) delete window[ZALO_FOLLOW_CALLBACK]
    }
  }, [attempt?.attempt_id, attempt?.oa_id, attempt?.status, onLinked, open])

  if (!open) return null
  const linked = attempt?.status === 'linked'
  const terminal = ['expired', 'superseded', 'conflict'].includes(attempt?.status)

  return (
    <div className="fixed inset-0 z-[105] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="zalo-link-title">
      <button type="button" className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Đóng" />
      <div className="relative w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
        <button type="button" onClick={onClose} className="absolute right-4 top-4 rounded-lg p-2 text-slate-400 hover:bg-slate-100" aria-label="Đóng"><X className="h-4 w-4" /></button>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-[#0068ff]">
          {linked ? <CheckCircle2 className="h-5 w-5" /> : <MessageCircle className="h-5 w-5" />}
        </div>
        <h2 id="zalo-link-title" className="mt-4 text-xl font-black text-slate-900">Liên kết chat Zalo OA</h2>

        {linked ? (
          <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            <p className="font-bold">Đã liên kết thành công</p>
            <p className="mt-1">Tin nhắn từ tài khoản Zalo này giờ có thể được nhận diện là tài khoản Advertising Agent của bạn.</p>
          </div>
        ) : (
          <>
            <p className="mt-3 text-sm leading-6 text-slate-600">Quan tâm Official Account <strong>{attempt?.oa_name || 'IOT Generation'}</strong>. Liên kết chỉ hoàn tất sau khi máy chủ nhận được sự kiện đã ký từ Zalo.</p>
            <div className="mt-4 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-center">
              {busy && !attempt ? (
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-[#0068ff]" />
              ) : (
                <>
                  <p className="text-xs font-bold uppercase tracking-wide text-blue-600">Official Account</p>
                  <p className="mt-1 font-black text-blue-950">{attempt?.oa_name || 'IOT Generation'}</p>
                  {attempt?.oa_id && <div className="mt-3 flex min-h-10 justify-center"><div className="zalo-follow-only-button" data-oaid={attempt.oa_id} data-callback={ZALO_FOLLOW_CALLBACK} /></div>}
                  {attempt?.oa_id && <a href={`https://zalo.me/${attempt.oa_id}`} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-xs font-bold text-blue-700 underline underline-offset-2">Mở {attempt?.oa_name || 'IOT Generation'} trong Zalo</a>}
                  {followTouched && <p className="mt-3 text-xs font-semibold text-blue-700">Đã nhận thao tác. Đang chờ Zalo xác nhận…</p>}
                </>
              )}
            </div>
            {attempt?.link_code && <details className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <summary className="cursor-pointer font-bold">Đã quan tâm OA hoặc nút không hoạt động?</summary>
              <p className="mt-3 leading-6">Gửi chính xác tin nhắn sau cho <strong>{attempt?.oa_name || 'IOT Generation'}</strong>. Mã chỉ dùng một lần và hết hạn sau 10 phút.</p>
              <p className="mt-3 rounded-xl bg-white px-3 py-3 text-center font-mono text-lg font-black tracking-wider text-slate-900">LINK {attempt.link_code}</p>
              <button type="button" onClick={async () => {
                await navigator.clipboard.writeText(`LINK ${attempt.link_code}`)
                setCopied(true)
              }} className="mx-auto mt-3 flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-bold text-blue-700 shadow-sm">
                <Copy className="h-3.5 w-3.5" /> {copied ? 'Đã sao chép' : 'Sao chép'}
              </button>
            </details>}
            {attempt?.status === 'pending' && <p className="mt-3 flex items-center justify-center gap-2 text-xs font-semibold text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Đang chờ tin nhắn đã xác thực từ Zalo…</p>}
            {terminal && <button type="button" onClick={createAttempt} disabled={busy} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-[#0068ff] px-4 py-2.5 text-sm font-bold text-white"><RefreshCw className="h-4 w-4" /> Tạo mã mới</button>}
          </>
        )}
        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button type="button" onClick={onClose} className="mt-5 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-50">{linked ? 'Hoàn tất' : 'Đóng'}</button>
      </div>
    </div>
  )
}
