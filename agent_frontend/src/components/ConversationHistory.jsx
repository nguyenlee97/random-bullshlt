import { Archive, Clock3, History, Loader2, MessageSquarePlus, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

const modeLabel = mode => mode === 'autopilot' ? 'Campaign Autopilot' : mode === 'guided' ? 'Campaign Copilot' : 'Chưa chọn cách làm việc'

const formatTime = value => {
  if (!value) return 'Chưa có tin nhắn'
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(value))
  } catch { return String(value) }
}

export default function ConversationHistory({
  open, onClose, conversations, currentId, loading, error,
  onResume, onNew, onArchive, onDelete, onDeleteAll,
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[80] flex justify-end bg-slate-950/30 backdrop-blur-[1px]" role="dialog" aria-modal="true" aria-label="Lịch sử chiến dịch">
      <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Đóng lịch sử" />
      <aside className="relative flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
            <History className="h-4.5 w-4.5" />
          </div>
          <div>
            <h2 className="font-bold text-slate-900">Lịch sử chiến dịch</h2>
            <p className="text-xs text-slate-500">Tiếp tục đúng workspace và tiến độ đã lưu</p>
          </div>
          <button onClick={onClose} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Đóng">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="border-b border-slate-100 p-4">
          <Button onClick={onNew} className="w-full gap-2 bg-brand-500 hover:bg-brand-600">
            <MessageSquarePlus className="h-4 w-4" />
            Tạo chiến dịch mới
          </Button>
          {conversations.length > 0 && (
            <button type="button" onClick={onDeleteAll}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-bold text-red-600 hover:bg-red-50"
              aria-label="Xóa toàn bộ lịch sử, kể cả cuộc trò chuyện đã lưu trữ">
              <Trash2 className="h-3.5 w-3.5" /> Xóa toàn bộ lịch sử
            </button>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Đang tải lịch sử…
            </div>
          )}
          {!loading && error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          {!loading && !error && conversations.length === 0 && (
            <div className="py-12 text-center text-sm text-slate-500">Chưa có chiến dịch nào được lưu.</div>
          )}
          <div className="space-y-2">
            {conversations.map(item => {
              const active = item.conversation_id === currentId
              return (
                <div key={item.conversation_id} className={`rounded-xl border p-3 transition ${active ? 'border-brand-300 bg-brand-50/60' : 'border-slate-200 hover:border-slate-300'}`}>
                  <button type="button" className="w-full text-left" onClick={() => onResume(item.conversation_id)} disabled={active}>
                    <div className="flex items-start gap-2">
                      <p className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">{item.title || 'Chiến dịch mới'}</p>
                      {active && <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-bold text-brand-700">Đang mở</span>}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                      <span>{modeLabel(item.experience_mode)}</span>
                      <span className="flex items-center gap-1"><Clock3 className="h-3 w-3" />{formatTime(item.last_message_at || item.updated_at)}</span>
                    </div>
                  </button>
                  <div className="mt-2 flex items-center gap-3">
                    {!active && (
                      <button type="button" onClick={() => onArchive(item.conversation_id)} className="flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-slate-700"
                        aria-label={`Lưu trữ ${item.title || 'campaign'}`}>
                        <Archive className="h-3 w-3" /> Lưu trữ
                      </button>
                    )}
                    <button type="button" onClick={() => onDelete(item)} className="flex items-center gap-1 text-[11px] font-semibold text-red-500 hover:text-red-700"
                      aria-label={`Xóa ${item.title || 'campaign'}`}>
                      <Trash2 className="h-3 w-3" /> Xóa
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </aside>
    </div>
  )
}
