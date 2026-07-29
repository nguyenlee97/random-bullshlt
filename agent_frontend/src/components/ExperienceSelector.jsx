import { useState } from 'react'
import {
  Archive, ArrowLeft, ArrowRight, Bot, Check, Clock3, History, Loader2,
  LogIn, Play, Route, Save, ShieldCheck, Sparkles, Trash2, Zap,
} from 'lucide-react'
import AccountMenu from '@/components/AccountMenu'
import ZaloOACompanion from '@/components/ZaloOACompanion'
import { partitionConversationHistory } from '@/lib/conversationHistory'

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
const runStatus = status => ({
  queued: ['Đang chờ', 'bg-slate-100 text-slate-700'],
  running: ['Đang chạy', 'bg-blue-50 text-blue-700'],
  waiting_review: ['Cần duyệt', 'bg-amber-50 text-amber-800'],
  paused: ['Đã tạm dừng', 'bg-amber-50 text-amber-800'],
  completed: ['Hoàn tất', 'bg-emerald-50 text-emerald-700'],
  failed: ['Có lỗi', 'bg-red-50 text-red-700'],
  cancelled: ['Đã hủy', 'bg-slate-100 text-slate-600'],
}[status] || [status || 'Chưa chạy', 'bg-slate-100 text-slate-600'])

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
  campaignEngineReady = false,
  historyError = '', onResume, onArchive, onDelete, onDeleteAll, onClaim,
  identity, identityBusy, onLogin, onLogout, onLoadSessions, onRevokeSession,
  onLinkZalo, onOpenZaloOA, onUnlinkZaloOA,
  onOpenDemo, onBackToLanding,
}) {
  const [historyView, setHistoryView] = useState('active')
  const { active: activeConversations, archived: archivedConversations } = partitionConversationHistory(conversations)
  const visibleConversations = historyView === 'archived' ? archivedConversations : activeConversations

  return (
    <main className="h-screen h-[100dvh] overflow-y-auto overscroll-contain bg-[#eef4fb] px-4 py-5 sm:px-8 sm:py-8">
      <div className="mx-auto max-w-6xl rounded-[28px] border border-white/80 bg-white/60 p-4 shadow-[0_30px_100px_rgba(22,70,130,0.10)] backdrop-blur-xl sm:p-7 lg:p-9">
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
          <div className="flex items-center gap-2">
            <button type="button" onClick={onBackToLanding} className="hidden items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold text-slate-500 hover:bg-white hover:text-brand-700 sm:inline-flex">
              <ArrowLeft className="h-3.5 w-3.5" /> Giới thiệu
            </button>
            <AccountMenu identity={identity} busy={identityBusy} onLogin={onLogin} onLogout={onLogout}
              onLoadSessions={onLoadSessions} onRevokeSession={onRevokeSession}
              onLinkZalo={onLinkZalo} onOpenZaloOA={onOpenZaloOA} onUnlinkZaloOA={onUnlinkZaloOA} />
          </div>
        </div>

        <section className="pt-10" aria-labelledby="home-title">
          <div className="grid items-end gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(310px,.8fr)]">
            <div>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
                <Zap className="h-3.5 w-3.5 text-orange-500" />
                Một brief. Một AI. Trọn hành trình campaign.
              </span>
              <h1 id="home-title" className="mt-4 max-w-3xl text-3xl font-black tracking-[-0.045em] text-slate-950 sm:text-5xl">
                Bạn muốn Agent<br className="hidden sm:block" /> đồng hành thế nào?
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
                Chọn một workspace để bắt đầu. Mỗi campaign giữ nguyên chat, dữ liệu và lịch sử dù bạn làm việc theo Copilot hay Autopilot.
              </p>
            </div>

          <div className={`flex flex-col gap-4 rounded-2xl border p-4 ${identity?.authenticated ? 'border-emerald-200 bg-emerald-50/80' : 'border-brand-200 bg-brand-50/70'}`} data-testid="identity-onboarding-card">
            <div className="flex items-start gap-3">
              <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${identity?.authenticated ? 'bg-emerald-100 text-emerald-700' : 'bg-brand-50 text-brand-700'}`}>
                {identity?.authenticated ? <ShieldCheck className="h-5 w-5" /> : <Zap className="h-5 w-5" />}
              </span>
              <div>
                <p className="text-sm font-black text-slate-900">{identity?.authenticated ? `Đã đồng bộ với ${identity.user?.display_name || 'tài khoản của bạn'}` : 'Bắt đầu ẩn danh — không cần đăng nhập'}</p>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">
                  {identity?.authenticated
                    ? 'Lịch sử đa thiết bị, danh tính Zalo và liên kết Zalo OA của bạn được quản lý bằng quyền sở hữu phía máy chủ.'
                    : 'Mọi tính năng tạo campaign vẫn dùng được trên thiết bị này. Đăng nhập Zalo chỉ cần khi bạn muốn đồng bộ lịch sử đa thiết bị và tiếp tục qua Zalo OA.'}
                </p>
              </div>
            </div>
            {!identity?.authenticated && (
              <button type="button" onClick={onLogin} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-brand-200 bg-white px-4 py-2.5 text-xs font-black text-brand-700 hover:bg-brand-50">
                <LogIn className="h-4 w-4" /> Đăng nhập Zalo (tuỳ chọn)
              </button>
            )}
          </div>
          </div>

          <div className="mt-10 flex items-end justify-between gap-4 border-t border-slate-200 pt-7">
            <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-brand-600">Workspace entrance</p><h2 className="mt-1 text-xl font-black text-slate-900">Chọn chế độ để mở campaign</h2></div>
            <p className="hidden max-w-sm text-right text-xs leading-5 text-slate-500 md:block">Guided tour sẽ hướng dẫn trực tiếp trên giao diện thật và dừng trước mọi hành động launch.</p>
          </div>

          <div className="mt-5 grid gap-5 md:grid-cols-2">
            {modes.map(mode => {
              const Icon = mode.icon
              return (
                <article
                  key={mode.id}
                  className="group flex min-h-[390px] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 text-left shadow-[0_14px_40px_rgba(28,62,104,0.08)] transition-all hover:-translate-y-1 hover:border-brand-300 hover:shadow-[0_24px_60px_rgba(0,104,255,0.16)] motion-reduce:transform-none"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-500 group-hover:text-white">
                      <Icon className="h-6 w-6" />
                    </div>
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">{mode.id === 'guided' ? 'Human-led' : 'Goal-led'}</span>
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
                  <div className="mt-auto grid gap-2 pt-6 sm:grid-cols-[minmax(0,1fr)_auto]">
                    <button type="button" disabled={busy || !campaignEngineReady} onClick={() => onSelect(mode.id)} aria-label={`Bắt đầu ${mode.title}: ${mode.description}`} className="inline-flex min-h-14 items-center justify-between gap-3 rounded-2xl bg-brand-500 px-5 py-3 text-sm font-black text-white shadow-[0_12px_28px_rgba(0,104,255,0.22)] hover:bg-brand-600 disabled:cursor-wait disabled:opacity-60">
                      <span className="text-left">Mở {mode.id === 'guided' ? 'Copilot workspace' : 'Autopilot workspace'}</span><ArrowRight className="h-5 w-5 shrink-0" />
                    </button>
                    <button type="button" onClick={() => onOpenDemo(mode.id === 'guided' ? 'copilot' : 'autopilot')} className="inline-flex min-h-14 items-center justify-center gap-2 rounded-2xl border border-slate-200 px-4 py-3 text-xs font-black text-slate-600 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700" aria-label={`Xem demo ${mode.title}`}>
                      <Play className="h-4 w-4" /> Guided tour
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
          {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        </section>

        <div className="mt-12 grid items-start gap-6 border-t border-slate-200/80 pt-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="pb-8" aria-labelledby="campaign-history-title">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-brand-600"><History className="h-4 w-4" /> Hành trình của bạn</p>
              <h2 id="campaign-history-title" className="mt-2 text-2xl font-black text-slate-900">Tiếp nối những campaign đang viết dở</h2>
              <p className="mt-1 text-sm text-slate-600">Mọi ý tưởng hay đều xứng đáng được đi đến cùng.</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-2">
              <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 shadow-sm">{activeConversations.length} đang hoạt động</span>
              {conversations.length > 0 && (
                <button type="button" onClick={onDeleteAll}
                  className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-bold text-red-600 hover:bg-red-50"
                  aria-label="Xóa toàn bộ lịch sử, kể cả cuộc trò chuyện đã lưu trữ">
                  <Trash2 className="h-3 w-3" /> Xóa tất cả
                </button>
              )}
            </div>
          </div>

          <div className="mt-5 inline-flex rounded-xl bg-slate-200/70 p-1" role="tablist" aria-label="Loại lịch sử chiến dịch">
            <button type="button" role="tab" aria-selected={historyView === 'active'} onClick={() => setHistoryView('active')}
              className={`rounded-lg px-3 py-2 text-xs font-bold transition ${historyView === 'active' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
              Đang hoạt động ({activeConversations.length})
            </button>
            <button type="button" role="tab" aria-selected={historyView === 'archived'} onClick={() => setHistoryView('archived')}
              className={`rounded-lg px-3 py-2 text-xs font-bold transition ${historyView === 'archived' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
              Đã lưu trữ ({archivedConversations.length})
            </button>
          </div>

          {historyLoading && (
            <div className="mt-5 flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white/70 py-10 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Đang tải lịch sử…
            </div>
          )}
          {!historyLoading && historyError && <p className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-700">{historyError}</p>}
          {!historyLoading && !historyError && visibleConversations.length === 0 && (
            <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-5 py-10 text-center text-sm text-slate-500">
              {historyView === 'archived'
                ? 'Chưa có campaign nào được lưu trữ.'
                : 'Campaign đầu tiên đang chờ bạn tạo dấu ấn. Bắt đầu ngay ở phía trên.'}
            </div>
          )}
          {!historyLoading && !historyError && visibleConversations.length > 0 && (
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {visibleConversations.map(item => {
                const run = item.latest_run_summary
                const [runLabel, runTone] = runStatus(run?.status)
                return <article key={item.conversation_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-200 hover:shadow-md">
                  <button type="button" className="w-full text-left" onClick={() => onResume(item.conversation_id)}>
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="min-w-0 flex-1 truncate text-sm font-bold text-slate-900">{item.title || 'Campaign mới'}</h3>
                      <div className="flex shrink-0 items-center gap-2">
                        {item.archived_at && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">Đã lưu trữ</span>}
                        <ArrowRight className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                      <span className="rounded-full bg-brand-50 px-2 py-0.5 font-bold text-brand-700">{modeLabel(item.experience_mode)}</span>
                      <span className={`rounded-full px-2 py-0.5 font-bold ${item.ownership === 'account' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                        {item.ownership === 'account' ? 'Tài khoản' : 'Trên thiết bị'}
                      </span>
                      <span className="flex items-center gap-1"><Clock3 className="h-3 w-3" />{formatTime(item.last_message_at || item.updated_at)}</span>
                    </div>
                    {run && (
                      <div className="mt-3 flex items-center gap-2" aria-label={`Tiến độ Autopilot: ${runLabel}`}>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${runTone}`}>{runLabel}</span>
                        <div className="h-1.5 min-w-16 flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div className="h-full rounded-full bg-brand-500 transition-all"
                            style={{ width: `${run.task_total ? Math.round((run.task_completed / run.task_total) * 100) : 0}%` }} />
                        </div>
                        <span className="text-[10px] font-semibold text-slate-500">{run.task_completed}/{run.task_total} bước</span>
                      </div>
                    )}
                  </button>
                  <div className="mt-3 flex items-center gap-3">
                    {item.can_claim && (
                      <button type="button" onClick={() => onClaim(item)} className="flex items-center gap-1 text-[11px] font-bold text-brand-600 hover:text-brand-800">
                        <Save className="h-3 w-3" /> Lưu vào tài khoản
                      </button>
                    )}
                    {!item.archived_at && (
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
                </article>
              })}
            </div>
          )}
        </section>
        <ZaloOACompanion identity={identity} onOpenZaloOA={onOpenZaloOA} />
        </div>

        <p className="mx-auto max-w-2xl pb-8 text-center text-[11px] leading-5 text-slate-500">
          Nội dung campaign được dịch vụ AI xử lý để lập kế hoạch và thực thi. Không nhập dữ liệu cá nhân hoặc bí mật không cần thiết.
        </p>
      </div>
    </main>
  )
}
