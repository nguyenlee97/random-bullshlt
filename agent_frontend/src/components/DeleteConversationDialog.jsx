import { useEffect, useState } from 'react'
import { AlertTriangle, Loader2, Trash2, X } from 'lucide-react'

const DELETE_ALL_PHRASE = 'XÓA TẤT CẢ'

export default function DeleteConversationDialog({
  target, busy = false, error = '', onCancel, onConfirm,
}) {
  const [phrase, setPhrase] = useState('')
  const deleteAll = target?.type === 'all'

  useEffect(() => setPhrase(''), [target])
  if (!target) return null

  const title = target.conversation?.title || 'Campaign chưa đặt tên'
  const phraseMatches = phrase.trim().toLocaleUpperCase('vi-VN') === DELETE_ALL_PHRASE
  const canConfirm = !busy && (!deleteAll || phraseMatches)

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-[2px]"
      role="alertdialog" aria-modal="true" aria-labelledby="delete-dialog-title" aria-describedby="delete-dialog-description">
      <button type="button" className="absolute inset-0 cursor-default" onClick={() => !busy && onCancel?.()} aria-label="Đóng hộp xác nhận xóa" />
      <section className="relative w-full max-w-md rounded-3xl border border-red-100 bg-white p-5 shadow-2xl sm:p-6">
        <button type="button" onClick={() => !busy && onCancel?.()} disabled={busy}
          className="absolute right-4 top-4 rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50" aria-label="Đóng">
          <X className="h-4 w-4" />
        </button>

        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red-50 text-red-600">
          {deleteAll ? <AlertTriangle className="h-6 w-6" /> : <Trash2 className="h-5 w-5" />}
        </div>
        <h2 id="delete-dialog-title" className="mt-4 pr-10 text-xl font-black text-slate-900">
          {deleteAll ? 'Xóa toàn bộ lịch sử?' : 'Xóa cuộc trò chuyện này?'}
        </h2>
        <div id="delete-dialog-description" className="mt-2 space-y-2 text-sm leading-6 text-slate-600">
          {deleteAll ? (
            <p>Bạn sắp xóa vĩnh viễn <strong className="text-slate-900">{target.count} cuộc trò chuyện đang hiển thị</strong> và mọi cuộc trò chuyện đã lưu trữ, gồm chat, workspace và dữ liệu Autopilot liên quan.</p>
          ) : (
            <p>“<strong className="text-slate-900">{title}</strong>” sẽ bị xóa vĩnh viễn cùng chat, workspace và dữ liệu Autopilot liên quan.</p>
          )}
          <p>Campaign/order đã tạo trong AdsPilot vẫn được giữ lại như hồ sơ kinh doanh. Thao tác này không thể hoàn tác.</p>
        </div>

        {deleteAll && (
          <label className="mt-4 block text-xs font-bold text-slate-700">
            Nhập <span className="text-red-600">{DELETE_ALL_PHRASE}</span> để xác nhận
            <input value={phrase} onChange={event => setPhrase(event.target.value)} disabled={busy} autoFocus
              className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm font-semibold outline-none focus:border-red-400 focus:ring-4 focus:ring-red-50 disabled:bg-slate-100"
              placeholder={DELETE_ALL_PHRASE} aria-label="Cụm từ xác nhận xóa toàn bộ" />
          </label>
        )}

        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">{error}</p>}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onCancel} disabled={busy}
            className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            Giữ lại
          </button>
          <button type="button" onClick={onConfirm} disabled={!canConfirm}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-slate-300">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            {deleteAll ? 'Xóa toàn bộ' : 'Xóa vĩnh viễn'}
          </button>
        </div>
      </section>
    </div>
  )
}
