import { Loader2, Save, X } from 'lucide-react'

export default function ClaimConversationDialog({ conversation, busy, error, onCancel, onConfirm }) {
  if (!conversation) return null
  return (
    <div className="fixed inset-0 z-[105] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="claim-title">
      <button type="button" className="absolute inset-0 cursor-default" onClick={busy ? undefined : onCancel} aria-label="Đóng" />
      <div className="relative w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
        <button type="button" onClick={onCancel} disabled={busy} className="absolute right-4 top-4 rounded-lg p-2 text-slate-400 hover:bg-slate-100" aria-label="Đóng">
          <X className="h-4 w-4" />
        </button>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-600"><Save className="h-5 w-5" /></div>
        <h2 id="claim-title" className="mt-4 text-xl font-black text-slate-900">Lưu campaign vào tài khoản?</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          <strong>{conversation.title || 'Campaign mới'}</strong> sẽ giữ nguyên chat, workspace, revision, creative và tiến độ Autopilot. Thao tác chỉ chuyển quyền sở hữu sang tài khoản đang đăng nhập.
        </p>
        {error && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" onClick={onCancel} disabled={busy} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-50">Để sau</button>
          <button type="button" onClick={onConfirm} disabled={busy} className="flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-bold text-white hover:bg-brand-600 disabled:opacity-70">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Lưu vào tài khoản
          </button>
        </div>
      </div>
    </div>
  )
}
