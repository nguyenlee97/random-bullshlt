import { useEffect, useState } from 'react'
import { CheckCircle2, Copy, Loader2, MessageCircle, RefreshCw, X } from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'

export default function ZaloLinkDialog({ open, onClose, onLinked }) {
  const [attempt, setAttempt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const createAttempt = async () => {
    setBusy(true)
    setError('')
    setCopied(false)
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
            <p className="mt-3 text-sm leading-6 text-slate-600">Mở Official Account đã cấu hình trong Zalo và gửi chính xác tin nhắn dưới đây. Mã chỉ dùng một lần và hết hạn sau 10 phút.</p>
            <div className="mt-4 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-center">
              {busy && !attempt ? (
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-[#0068ff]" />
              ) : (
                <>
                  <p className="text-xs font-bold uppercase tracking-wide text-blue-600">Tin nhắn cần gửi</p>
                  <p className="mt-2 font-mono text-xl font-black tracking-wider text-blue-950">LINK {attempt?.link_code || '—'}</p>
                  {attempt?.link_code && (
                    <button type="button" onClick={async () => {
                      await navigator.clipboard.writeText(`LINK ${attempt.link_code}`)
                      setCopied(true)
                    }} className="mx-auto mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-bold text-blue-700 shadow-sm">
                      <Copy className="h-3.5 w-3.5" /> {copied ? 'Đã sao chép' : 'Sao chép'}
                    </button>
                  )}
                </>
              )}
            </div>
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
