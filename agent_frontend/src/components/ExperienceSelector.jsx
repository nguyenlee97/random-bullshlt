import {
  Archive, ArrowRight, Bot, Check, Clock3, History, Loader2,
  Route, Save, Sparkles, Trash2, Zap,
} from 'lucide-react'
import AccountMenu from '@/components/AccountMenu'

const modes = [
  {
    id: 'guided',
    title: 'Campaign Copilot',
    eyebrow: 'Sức mạnh AI · Dấu ấn của bạn',
    description: 'Cùng Agent biến tư duy chiến lược của bạn thành một campaign sắc nét. Bạn dẫn lối, AI mở rộng góc nhìn và đưa từng ý tưởng tiến gần hơn đến phiên bản tốt nhất.',
    icon: Route,
    features: ['Làm chủ chiến lược ở mọi chặng', 'Khơi mở audience và creative giàu tiềm năng', 'Tinh chỉnh linh hoạt cho đến khi thật sự ưng ý'],
  },
  {
    id: 'autopilot',
    title: 'Campaign Autopilot',
    eyebrow: 'Trao mục tiêu · Nhận campaign hoàn chỉnh',
    description: 'Đưa cho Agent một brief. AI sẽ kết nối chiến lược, audience, creative và media thành một campaign liền mạch, sẵn sàng để bạn đưa ra quyết định cuối cùng.',
    icon: Sparkles,
    features: ['Từ brief đến kế hoạch chỉ trong một mạch', 'Ra quyết định dựa trên dữ liệu và tín hiệu thực', 'Tăng tốc launch mà vẫn giữ quyền kiểm soát'],
  },
]

const modeLabel = mode => mode === 'autopilot' ? 'Campaign Autopilot' : 'Campaign Copilot'

const formatTime = value => {
  if (!value) return 'Chưa có tin nhắn'
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(value))
  } catch { return String(value) }
}

export default function ExperienceSelector({
  onSelect, busy, error, conversations = [], historyLoading = false,
  historyError = '', onResume, onArchive, onDelete, onDeleteAll, onClaim,
  identity, identityBusy, onLogin, onLogout, onLoadSessions, onRevokeSession,
  onLinkZalo, onOpenZaloOA, onUnlinkZaloOA,
}) {
  return (
    <main className="h-screen h-[100dvh] overflow-y-auto overscroll-contain bg-[radial-gradient(circle_at_top_left,_#dcebff_0,_#f4f7fb_38%,_#eef4fb_100%)] px-5 py-8 sm:px-8 sm:py-12">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-500 shadow-[0_12px_30px_rgba(0,104,255,0.28)]">
              <Bot className="h-6 w-6 text-white" strokeWidth={2.3} />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-600">Advertising Agent</p>
              <p className="text-sm text-slate-600">Từ ý tưởng lớn đến campaign bứt phá</p>
            </div>
          </div>
          <AccountMenu identity={identity} busy={identityBusy} onLogin={onLogin} onLogout={onLogout}
            onLoadSessions={onLoadSessions} onRevokeSession={onRevokeSession}
            onLinkZalo={onLinkZalo} onOpenZaloOA={onOpenZaloOA} onUnlinkZaloOA={onUnlinkZaloOA} />
        </div>

        <section className="pt-12 sm:pt-16" aria-labelledby="home-title">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-white/80 px-3 py-1 text-xs font-semibold text-brand-700 shadow-sm">
            <Zap className="h-3.5 w-3.5 text-orange-500" />
            Một brief. Một AI. Trọn hành trình campaign.
          </span>
          <h1 id="home-title" className="mt-4 max-w-3xl text-3xl font-black tracking-tight text-slate-900 sm:text-5xl">
            Biến ý tưởng thành campaign tạo khác biệt
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">
            Camp Ads Agent đồng hành từ chiến lược, audience, creative đến vị trí hiển thị — để mỗi campaign được lên nhanh hơn, đúng người hơn và sẵn sàng tạo dấu ấn.
          </p>

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {modes.map(mode => {
              const Icon = mode.icon
              return (
                <button
                  key={mode.id}
                  type="button"
                  disabled={busy}
                  onClick={() => onSelect(mode.id)}
                  aria-label={`Bắt đầu ${mode.title}: ${mode.description}`}
                  className="group flex min-h-[300px] flex-col rounded-3xl border border-slate-200 bg-white p-6 text-left shadow-[0_12px_40px_rgba(28,62,104,0.08)] transition-all hover:-translate-y-1 hover:border-brand-300 hover:shadow-[0_20px_50px_rgba(0,104,255,0.16)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-200 disabled:cursor-wait disabled:opacity-70"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-500 group-hover:text-white">
                      <Icon className="h-6 w-6" />
                    </div>
                    <ArrowRight className="h-5 w-5 text-slate-300 transition-transform group-hover:translate-x-1 group-hover:text-brand-500" />
                  </div>
                  <p className="mt-6 text-xs font-bold uppercase tracking-[0.16em] text-brand-600">{mode.eyebrow}</p>
                  <h2 className="mt-2 text-2xl font-extrabold text-slate-900">{mode.title}</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-600">{mode.description}</p>
                  <ul className="mt-5 space-y-2.5">
                    {mode.features.map(feature => (
                      <li key={feature} className="flex items-start gap-2 text-sm text-slate-600">
                        <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                          <Check className="h-3 w-3" strokeWidth={3} />
                        </span>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </button>
              )
            })}
          </div>
          {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        </section>

        <section className="mt-14 border-t border-slate-200/80 pt-8 pb-8" aria-labelledby="campaign-history-title">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-brand-600"><History className="h-4 w-4" /> Hành trình của bạn</p>
              <h2 id="campaign-history-title" className="mt-2 text-2xl font-black text-slate-900">Tiếp nối những campaign đang viết dở</h2>
              <p className="mt-1 text-sm text-slate-600">Mọi ý tưởng hay đều xứng đáng được đi đến cùng.</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-2">
              <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 shadow-sm">{conversations.length} campaign</span>
              {conversations.length > 0 && (
                <button type="button" onClick={onDeleteAll}
                  className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-bold text-red-600 hover:bg-red-50"
                  aria-label="Xóa toàn bộ lịch sử, kể cả cuộc trò chuyện đã lưu trữ">
                  <Trash2 className="h-3 w-3" /> Xóa tất cả
                </button>
              )}
            </div>
          </div>

          {historyLoading && (
            <div className="mt-5 flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white/70 py-10 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Đang tải lịch sử…
            </div>
          )}
          {!historyLoading && historyError && <p className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-700">{historyError}</p>}
          {!historyLoading && !historyError && conversations.length === 0 && (
            <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-5 py-10 text-center text-sm text-slate-500">
              Campaign đầu tiên đang chờ bạn tạo dấu ấn. Bắt đầu ngay ở phía trên.
            </div>
          )}
          {!historyLoading && !historyError && conversations.length > 0 && (
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {conversations.map(item => (
                <article key={item.conversation_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-200 hover:shadow-md">
                  <button type="button" className="w-full text-left" onClick={() => onResume(item.conversation_id)}>
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="min-w-0 flex-1 truncate text-sm font-bold text-slate-900">{item.title || 'Campaign mới'}</h3>
                      <ArrowRight className="h-4 w-4 shrink-0 text-slate-300" />
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                      <span className="rounded-full bg-brand-50 px-2 py-0.5 font-bold text-brand-700">{modeLabel(item.experience_mode)}</span>
                      <span className={`rounded-full px-2 py-0.5 font-bold ${item.ownership === 'account' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                        {item.ownership === 'account' ? 'Tài khoản' : 'Trên thiết bị'}
                      </span>
                      <span className="flex items-center gap-1"><Clock3 className="h-3 w-3" />{formatTime(item.last_message_at || item.updated_at)}</span>
                    </div>
                  </button>
                  <div className="mt-3 flex items-center gap-3">
                    {item.can_claim && (
                      <button type="button" onClick={() => onClaim(item)} className="flex items-center gap-1 text-[11px] font-bold text-brand-600 hover:text-brand-800">
                        <Save className="h-3 w-3" /> Lưu vào tài khoản
                      </button>
                    )}
                    <button type="button" onClick={() => onArchive(item.conversation_id)} className="flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-slate-700"
                      aria-label={`Lưu trữ ${item.title || 'campaign'}`}>
                      <Archive className="h-3 w-3" /> Lưu trữ
                    </button>
                    <button type="button" onClick={() => onDelete(item)} className="flex items-center gap-1 text-[11px] font-semibold text-red-500 hover:text-red-700"
                      aria-label={`Xóa ${item.title || 'campaign'}`}>
                      <Trash2 className="h-3 w-3" /> Xóa
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <p className="mx-auto max-w-2xl pb-8 text-center text-[11px] leading-5 text-slate-500">
          Nội dung campaign được dịch vụ AI xử lý để lập kế hoạch và thực thi. Không nhập dữ liệu cá nhân hoặc bí mật không cần thiết.
        </p>
      </div>
    </main>
  )
}
