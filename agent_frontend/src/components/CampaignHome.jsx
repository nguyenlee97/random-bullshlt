import { useEffect, useMemo, useState } from 'react'
import {
  Archive, ArrowLeft, ArrowRight, Bot, ChevronLeft, ChevronRight, FilePenLine,
  History, LineChart, Loader2, LogIn, MessageCircleMore, MoreHorizontal, Search,
  Sparkles, Trash2, TriangleAlert, X, Zap,
} from 'lucide-react'
import AccountMenu from '@/components/AccountMenu'

const ZALO_OA_ID = import.meta.env.VITE_ZALO_OA_ID || '2224936774907333597'
const ZALO_OA_URL = `https://zalo.me/${ZALO_OA_ID}`

const money = value => Number.isFinite(Number(value))
  ? new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(value)) + ' ₫'
  : '—'

const time = value => {
  if (!value) return 'Vừa cập nhật'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(date)
}

const lifecycle = value => ({
  draft: ['BẢN NHÁP', 'border-blue-200 bg-blue-50 text-blue-700', 'bg-blue-500'],
  needs_review: ['CHỜ DUYỆT', 'border-amber-200 bg-amber-50 text-amber-800', 'bg-amber-500'],
  operational: ['ĐÃ TẠO', 'border-emerald-200 bg-emerald-50 text-emerald-700', 'bg-emerald-500'],
  active: ['ĐANG VẬN HÀNH', 'border-emerald-200 bg-emerald-50 text-emerald-700', 'bg-emerald-500'],
  paused: ['TẠM DỪNG', 'border-slate-200 bg-slate-100 text-slate-700', 'bg-slate-400'],
  completed: ['HOÀN TẤT', 'border-violet-200 bg-violet-50 text-violet-700', 'bg-violet-500'],
  failed: ['CÓ LỖI', 'border-red-200 bg-red-50 text-red-700', 'bg-red-500'],
  archived: ['LƯU TRỮ', 'border-slate-200 bg-slate-100 text-slate-500', 'bg-slate-400'],
}[value] || ['CAMPAIGN', 'border-slate-200 bg-slate-50 text-slate-600', 'bg-slate-400'])

const activityLabel = value => ({
  queued: 'Agent đang chờ', running: 'Agent đang chạy', waiting_review: 'Cần bạn quyết định',
  paused: 'Flow tạm dừng', failed: 'Run cần xử lý', cancelled: 'Run đã hủy',
  completed: 'Flow đã hoàn tất', editing: 'Đang chỉnh sửa', none: '',
}[value] || '')

const isOperational = item => item.phase === 'operational'
  || ['operational', 'active', 'completed'].includes(item.lifecycle)
const clampProgress = value => Math.max(0, Math.min(100, Number(value) || 0))

function useCampaignPageSize() {
  const read = () => typeof window !== 'undefined' && window.matchMedia?.('(max-width: 700px)').matches ? 1 : 2
  const [pageSize, setPageSize] = useState(read)

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined
    const media = window.matchMedia('(max-width: 700px)')
    const sync = () => setPageSize(media.matches ? 1 : 2)
    media.addEventListener?.('change', sync)
    return () => media.removeEventListener?.('change', sync)
  }, [])
  return pageSize
}

function CampaignCard({ item, onOpen, onOpenHistory, onArchive, onDelete, onClaim }) {
  const [statusLabel, statusTone, statusDot] = lifecycle(item.lifecycle)
  const activity = activityLabel(item.activity)
  const live = item.lifecycle !== 'archived' && isOperational(item)
  const review = item.lifecycle === 'needs_review'
  const progress = live ? 100 : clampProgress(item.progress?.percent)
  const primary = item.routes?.manage ? 'Quản lý campaign' : review ? 'Duyệt ngay' : item.read_only ? 'Xem kết quả' : 'Tiếp tục campaign'
  const cardTone = live
    ? 'border-[#164a89] bg-[linear-gradient(125deg,#071a3c,#0b326b_64%,#0757b9)] shadow-[0_22px_52px_rgba(4,28,67,.20)] sm:col-span-2'
    : review
      ? 'border-amber-200 bg-[linear-gradient(135deg,#fffdf7,#fff8e8)] sm:col-span-2'
      : 'border-slate-200 bg-white/90'
  const titleTone = live ? 'text-white' : 'text-slate-950'
  const metaTone = live ? 'text-blue-100/80' : 'text-slate-500'
  const secondaryTone = live
    ? 'border-white/20 bg-white/10 text-blue-50 hover:bg-white/15'
    : 'border-slate-200 bg-white/80 text-slate-600 hover:bg-slate-50'

  return (
    <article className={`relative rounded-[22px] border p-5 shadow-[0_12px_34px_rgba(27,59,102,.07)] transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_46px_rgba(27,59,102,.12)] ${cardTone}`}>
      <div className="flex items-start gap-3">
        <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] ${live ? 'bg-white/12 text-blue-100' : item.experience_mode === 'autopilot' ? 'bg-violet-100 text-violet-700' : 'bg-blue-50 text-brand-600'}`}>
          {item.experience_mode === 'autopilot' ? <Sparkles className="h-5 w-5" /> : <MessageCircleMore className="h-5 w-5" />}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className={`truncate text-[15.5px] font-black tracking-[-.025em] ${titleTone}`}>{item.title || 'Campaign mới'}</h3>
          <p className={`mt-1.5 text-[11.5px] leading-5 ${metaTone}`}>
            {activity || (live ? 'Campaign đã sẵn sàng để theo dõi và tối ưu' : 'Đang chỉnh sửa')}
            {item.progress?.current_label ? ` · ${item.progress.current_label}` : ''}
            {' · '}{time(item.updated_at)}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        <span className={`inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[10px] font-black ${statusTone}`}><span className={`h-1.5 w-1.5 rounded-full ${statusDot}`} />{statusLabel}</span>
        <span className={`inline-flex h-6 items-center rounded-full px-2.5 text-[10px] font-black ${live ? 'bg-white/12 text-blue-50' : item.experience_mode === 'autopilot' ? 'bg-violet-50 text-violet-700' : 'bg-blue-50 text-blue-700'}`}>{item.experience_mode === 'autopilot' ? 'AUTOPILOT' : 'COPILOT'}</span>
        <span className={`inline-flex h-6 items-center rounded-full border px-2.5 text-[10px] font-bold ${live ? 'border-white/15 bg-white/10 text-blue-100' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>{item.ownership === 'account' ? 'Tài khoản' : item.ownership === 'device' ? 'Thiết bị này' : 'Workspace'}</span>
      </div>

      {item.progress && !live && (
        <div className="mt-4" aria-label={`Tiến độ ${progress} phần trăm`}>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${review ? 'bg-amber-500' : 'bg-brand-500'}`} style={{ width: `${progress}%` }} /></div>
          <div className="mt-2 flex justify-between text-[10.5px] font-bold text-slate-500"><span>{item.progress.completed || 0}/{item.progress.total || '—'} bước</span><span>{progress}%</span></div>
        </div>
      )}

      {item.order && (
        <div className={`mt-4 flex flex-wrap gap-2 text-[10.5px] ${live ? 'text-blue-100' : 'text-slate-600'}`}>
          <span className={`rounded-lg px-2.5 py-2 ${live ? 'bg-white/10' : 'bg-slate-50'}`}><strong className={titleTone}>{money(item.order.budget)}</strong> ngân sách</span>
          <span className={`rounded-lg px-2.5 py-2 ${live ? 'bg-white/10' : 'bg-slate-50'}`}><strong className={titleTone}>{item.order.placement_count ?? '—'}</strong> placement</span>
          <span className={`rounded-lg px-2.5 py-2 ${live ? 'bg-white/10' : 'bg-slate-50'}`}><strong className={titleTone}>{item.order.creative_count ?? '—'}</strong> creative</span>
        </div>
      )}

      <div className="mt-[18px] flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => onOpen(item)} className={`inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-black sm:flex-none ${live ? 'border-white bg-white text-[#0b326b] hover:bg-blue-50' : review ? 'border-amber-700 bg-amber-700 text-white hover:bg-amber-800' : 'border-brand-500 bg-brand-500 text-white hover:bg-brand-600'}`}>{primary}<ArrowRight className="h-4 w-4" /></button>
        {item.routes?.conversation && item.routes?.manage && <button type="button" onClick={() => onOpenHistory(item)} className={`inline-flex min-h-10 items-center justify-center gap-1.5 rounded-xl border px-3 text-[11.5px] font-bold max-sm:order-3 max-sm:w-full ${secondaryTone}`}><History className="h-4 w-4" /> Xem flow đã hoàn tất</button>}
        <details className="group/menu relative ml-auto">
          <summary className={`flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-xl border [&::-webkit-details-marker]:hidden ${secondaryTone}`} aria-label={`Thao tác khác cho ${item.title || 'campaign'}`}><MoreHorizontal className="h-4 w-4" /></summary>
          <div className="absolute bottom-12 right-0 z-30 w-56 rounded-xl border border-slate-200 bg-white p-1 shadow-2xl">
            {item.can_claim && <button type="button" onClick={() => onClaim(item)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-semibold text-brand-700 hover:bg-brand-50"><LogIn className="h-4 w-4" /> Gắn vào tài khoản…</button>}
            {!item.archived_at && item.conversation_id && <button type="button" onClick={() => onArchive(item.conversation_id)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-semibold text-slate-600 hover:bg-slate-50"><Archive className="h-4 w-4" /> Lưu trữ</button>}
            {item.conversation_id && <button type="button" onClick={() => onDelete(item)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-semibold text-red-600 hover:bg-red-50"><Trash2 className="h-4 w-4" /> {live ? 'Xóa lịch sử làm việc…' : 'Xóa bản nháp…'}</button>}
          </div>
        </details>
      </div>
    </article>
  )
}

function CampaignGroup({ definition, page, pageSize, direction, onPageChange, cardProps }) {
  const pageCount = Math.max(1, Math.ceil(definition.rows.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const first = safePage * pageSize
  const rows = definition.rows.slice(first, first + pageSize)
  const Icon = definition.icon
  if (!definition.rows.length) return null

  return (
    <section className="mt-8" aria-labelledby={`${definition.id}-title`}>
      <div className="mb-3 flex items-end gap-3.5">
        <span className={`flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[13px] ${definition.iconTone}`}><Icon className="h-[18px] w-[18px]" /></span>
        <div><p className={`text-[9.5px] font-black uppercase tracking-[.16em] ${definition.eyebrowTone}`}>{definition.eyebrow}</p><h2 id={`${definition.id}-title`} className="mt-0.5 text-lg font-black tracking-[-.025em] text-slate-900">{definition.title} · {definition.rows.length}</h2></div>
        <p className="ml-auto mb-0.5 hidden max-w-[460px] text-right text-[11.5px] leading-5 text-slate-500 lg:block">{definition.description}</p>
      </div>
      <div key={`${definition.id}-${safePage}-${pageSize}`} className={`grid gap-[13px] sm:grid-cols-2 ${direction === 'prev' ? 'campaign-page-slide-prev' : 'campaign-page-slide-next'}`} data-page={safePage + 1}>
        {rows.map(item => <CampaignCard key={item.entry_id} item={item} {...cardProps} />)}
      </div>
      {pageCount > 1 && (
        <div className="mt-3 flex items-center justify-between gap-3 px-0.5" aria-label={`Phân trang ${definition.title}`}>
          <span className="text-[10.5px] font-bold text-slate-500">Hiển thị {first + 1}–{Math.min(first + pageSize, definition.rows.length)} trong {definition.rows.length} campaign</span>
          <div className="flex items-center gap-1.5">
            <button type="button" disabled={safePage === 0} onClick={() => onPageChange(definition.id, safePage - 1, 'prev')} aria-label={`Trang trước của ${definition.title}`} className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-slate-300 bg-white/80 text-slate-600 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-default disabled:opacity-35"><ChevronLeft className="h-4 w-4" /></button>
            <span className="min-w-[62px] text-center text-[10.5px] font-black text-slate-700">{safePage + 1} / {pageCount}</span>
            <button type="button" disabled={safePage >= pageCount - 1} onClick={() => onPageChange(definition.id, safePage + 1, 'next')} aria-label={`Trang sau của ${definition.title}`} className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-slate-300 bg-white/80 text-slate-600 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-default disabled:opacity-35"><ChevronRight className="h-4 w-4" /></button>
          </div>
        </div>
      )}
    </section>
  )
}

function ZaloContinuityNudge({ identity, onLogin, onLinkZalo, onOpenZaloOA }) {
  const [visible, setVisible] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  useEffect(() => {
    if (dismissed) return undefined
    const timer = window.setTimeout(() => setVisible(true), 2600)
    return () => window.clearTimeout(timer)
  }, [dismissed])
  if (!visible || dismissed || !identity) return null

  const providers = identity.user?.providers || []
  const hasZaloLogin = providers.includes('zalo')
  const hasZaloOA = Boolean(identity.channels?.zalo_oa)
  const dismiss = () => { setVisible(false); setDismissed(true) }
  const run = callback => { dismiss(); callback?.() }
  let title = 'Tiếp tục campaign ở bất cứ đâu'
  let copy = 'Đăng nhập Zalo để đồng bộ campaign giữa các thiết bị và tiếp tục trò chuyện với Agent qua Zalo OA.'
  let actionLabel = 'Đăng nhập Zalo'
  let action = () => run(onLogin)

  if (identity.authenticated && !hasZaloLogin) {
    title = 'Kết nối campaign với Zalo'
    copy = 'Gắn Zalo Login vào tài khoản hiện tại để đồng bộ đa thiết bị, sau đó liên kết OA để tiếp tục trò chuyện.'
    actionLabel = 'Kết nối Zalo'
    action = () => run(onLinkZalo)
  } else if (identity.authenticated && !hasZaloOA) {
    title = 'Hoàn tất Zalo continuity'
    copy = 'Campaign đã đồng bộ đa thiết bị. Liên kết OA IOT Generation để hỏi trạng thái và nhận checkpoint qua Zalo.'
    actionLabel = 'Liên kết Zalo OA'
    action = () => run(onOpenZaloOA)
  } else if (identity.authenticated && hasZaloOA) {
    title = 'Mang Campaign Agent theo bạn'
    copy = 'Campaign đã được đồng bộ. Mở Zalo OA để hỏi trạng thái và tiếp tục trao đổi khi rời workspace.'
    actionLabel = 'Mở Zalo OA'
    action = null
  }

  return (
    <aside className="campaign-zalo-nudge fixed bottom-[calc(14px+env(safe-area-inset-bottom))] right-3.5 z-[58] w-[342px] max-w-[calc(100vw-28px)] overflow-hidden rounded-[20px] border border-blue-300/70 bg-white/95 shadow-[0_24px_64px_rgba(15,52,104,.22)] backdrop-blur-xl sm:bottom-[calc(22px+env(safe-area-inset-bottom))] sm:right-[22px]" aria-label="Tiếp tục cùng Agent trên Zalo" aria-live="polite">
      <span className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-[#0068ff] to-violet-600" />
      <button type="button" onClick={dismiss} className="absolute right-2.5 top-2.5 flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100" aria-label="Đóng hướng dẫn Zalo"><X className="h-4 w-4" /></button>
      <div className="flex gap-3 px-[18px] pb-3.5 pl-5 pt-[17px]"><span className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-blue-50 to-violet-100 text-[#0068ff]"><MessageCircleMore className="h-[21px] w-[21px]" /></span><div className="min-w-0 pr-[18px]"><p className="text-[9px] font-black uppercase tracking-[.14em] text-[#0068ff]">Zalo continuity</p><h2 className="mt-1 text-[13.5px] font-black tracking-[-.015em] text-slate-900">{title}</h2><p className="mt-1 text-[11.5px] leading-[1.6] text-slate-500">{copy}</p></div></div>
      <div className="flex items-center gap-2 pb-4 pl-[74px] pr-[18px]">
        {action ? <button type="button" onClick={action} className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-[10px] bg-[#0068ff] px-3.5 text-[11.5px] font-black text-white hover:bg-[#0055d4]">{actionLabel}<ArrowRight className="h-3.5 w-3.5" /></button> : <a href={ZALO_OA_URL} target="_blank" rel="noreferrer" onClick={dismiss} className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-[10px] bg-[#0068ff] px-3.5 text-[11.5px] font-black text-white hover:bg-[#0055d4]">{actionLabel}<ArrowRight className="h-3.5 w-3.5" /></a>}
        <button type="button" onClick={dismiss} className="text-[10.5px] font-bold text-slate-500 hover:text-slate-700">Để sau</button>
      </div>
    </aside>
  )
}

export default function CampaignHome({
  campaigns = [], loading, error, createDisabled, createError, onRefresh, onCreate, onOpen, onOpenHistory,
  onArchive, onDelete, onDeleteAll, onClaim,
  identity, identityBusy, onLogin, onLogout, onLoadSessions, onRevokeSession,
  onLinkZalo, onOpenZaloOA, onUnlinkZaloOA, onBackToLanding,
}) {
  const [tab, setTab] = useState('active')
  const [query, setQuery] = useState('')
  const [pages, setPages] = useState({ attention: 0, drafts: 0, live: 0, archive: 0 })
  const [pageDirections, setPageDirections] = useState({ attention: 'next', drafts: 'next', live: 'next', archive: 'next' })
  const pageSize = useCampaignPageSize()
  const archived = campaigns.filter(item => item.lifecycle === 'archived')
  const active = campaigns.filter(item => item.lifecycle !== 'archived')
  const normalized = query.trim().toLocaleLowerCase('vi')
  const matchesQuery = item => !normalized || [item.title, item.brand, item.campaign_id, item.experience_mode].filter(Boolean).join(' ').toLocaleLowerCase('vi').includes(normalized)
  const visibleActive = active.filter(matchesQuery)
  const visibleArchived = archived.filter(matchesQuery)
  const reviewCount = active.filter(item => item.lifecycle === 'needs_review').length
  const liveCount = active.filter(isOperational).length
  const draftCount = active.length - reviewCount - liveCount

  const groups = useMemo(() => tab === 'archived' ? [{
    id: 'archive', title: 'Campaign đã lưu trữ', eyebrow: 'Archive', description: 'Các campaign đã dọn khỏi workspace chính nhưng vẫn có thể mở lại để xem lịch sử.',
    icon: Archive, iconTone: 'bg-slate-200 text-slate-600', eyebrowTone: 'text-slate-500', rows: visibleArchived,
  }] : [{
    id: 'attention', title: 'Cần bạn xử lý', eyebrow: 'Your decision', description: 'Agent đã chuẩn bị xong ngữ cảnh và đang chờ một quyết định để tiếp tục.',
    icon: TriangleAlert, iconTone: 'bg-amber-100 text-amber-700', eyebrowTone: 'text-amber-700', rows: visibleActive.filter(item => item.lifecycle === 'needs_review'),
  }, {
    id: 'drafts', title: 'Đang được xây dựng', eyebrow: 'In progress', description: 'Những campaign còn dang dở — mở lại đúng bước, không mất chat hay campaign context.',
    icon: FilePenLine, iconTone: 'bg-blue-50 text-brand-600', eyebrowTone: 'text-brand-600', rows: visibleActive.filter(item => item.lifecycle !== 'needs_review' && !isOperational(item)),
  }, {
    id: 'live', title: 'Đang vận hành', eyebrow: 'Campaign operations', description: 'Đi vào trang quản lý riêng để xem setup, báo cáo, bằng chứng và trao đổi với Campaign Agent.',
    icon: LineChart, iconTone: 'bg-emerald-100 text-emerald-700', eyebrowTone: 'text-emerald-700', rows: visibleActive.filter(isOperational),
  }], [tab, visibleActive, visibleArchived])

  useEffect(() => {
    setPages({ attention: 0, drafts: 0, live: 0, archive: 0 })
    setPageDirections({ attention: 'next', drafts: 'next', live: 'next', archive: 'next' })
  }, [tab, query, pageSize])

  const changePage = (id, target, direction) => {
    setPageDirections(current => ({ ...current, [id]: direction }))
    setPages(current => ({ ...current, [id]: target }))
  }
  const cardProps = { onOpen, onOpenHistory, onArchive, onDelete, onClaim }
  const hasVisibleRows = groups.some(group => group.rows.length)

  return (
    <main className="min-h-screen overflow-x-hidden bg-[radial-gradient(circle_at_15%_0%,rgba(255,255,255,.95),rgba(255,255,255,0)_34%),linear-gradient(180deg,#edf5ff_0,#eef2f8_620px)] text-slate-900">
      <header className="sticky top-0 z-40 flex h-[72px] items-center gap-3.5 border-b border-slate-300/70 bg-white/75 px-[clamp(18px,4vw,42px)] shadow-[0_8px_30px_rgba(15,40,80,.05)] backdrop-blur-xl">
        <button type="button" onClick={onBackToLanding} className="flex min-w-0 items-center gap-2.5 text-left" title="Về trang giới thiệu"><span className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-[14px] bg-brand-500 shadow-[0_12px_28px_rgba(0,104,255,.24)]"><Bot className="h-5 w-5 text-white" /></span><span className="hidden min-w-0 flex-col gap-0.5 sm:flex"><span className="truncate text-[13px] font-black uppercase tracking-[.16em] text-brand-600">Advertising Agent</span><span className="truncate text-[11.5px] text-slate-500">Từ ý tưởng lớn đến campaign bứt phá</span></span></button>
        <div className="ml-auto flex items-center gap-2"><button type="button" onClick={onBackToLanding} className="hidden items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold text-slate-500 hover:bg-slate-100 lg:flex"><ArrowLeft className="h-4 w-4" /> Giới thiệu</button><AccountMenu identity={identity} busy={identityBusy} onLogin={onLogin} onLogout={onLogout} onLoadSessions={onLoadSessions} onRevokeSession={onRevokeSession} onLinkZalo={onLinkZalo} onOpenZaloOA={onOpenZaloOA} onUnlinkZaloOA={onUnlinkZaloOA} /></div>
      </header>

      <div className="mx-auto max-w-[1160px] px-[clamp(14px,3vw,28px)] pb-24 pt-6">
        <section className="relative overflow-hidden rounded-[28px] border border-white/90 bg-white/65 p-[clamp(24px,4vw,46px)] shadow-[0_30px_100px_rgba(22,70,130,.10)] backdrop-blur-xl" aria-labelledby="campaign-home-title">
          <span className="pointer-events-none absolute -right-[150px] -top-[190px] h-[360px] w-[360px] rounded-full bg-[radial-gradient(circle,rgba(0,104,255,.18),rgba(0,104,255,0)_68%)]" />
          <div className="relative grid items-center gap-8 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,.92fr)] lg:gap-[clamp(28px,5vw,62px)]">
            <div><span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 text-[11px] font-black uppercase tracking-[.08em] text-blue-800"><Zap className="h-3.5 w-3.5" /> Campaign command center</span><h1 id="campaign-home-title" className="mt-[18px] max-w-[680px] text-[clamp(34px,5vw,58px)] font-black leading-[.98] tracking-[-.055em] text-[#071226]">Mọi campaign.<br /> Một nơi để tiếp tục.</h1><p className="mt-[18px] max-w-[650px] text-[15px] leading-7 text-slate-600">Bắt đầu campaign mới, tiếp tục đúng bước đang làm và quản lý campaign đã vận hành — cùng một workspace, không mất chat hay campaign context.</p><span className="sr-only">Campaign của bạn · Tạo campaign mới · Bản nháp, tiến độ Agent</span></div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <button type="button" disabled={createDisabled} onClick={() => onCreate('guided')} className="grid min-h-[92px] grid-cols-[46px_minmax(0,1fr)_auto] items-center gap-3 rounded-[20px] border border-blue-200 bg-gradient-to-br from-white to-blue-50 p-4 text-left shadow-[0_16px_34px_rgba(0,104,255,.10)] transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-[0_22px_44px_rgba(0,104,255,.16)] disabled:cursor-not-allowed disabled:opacity-50"><span className="flex h-[46px] w-[46px] items-center justify-center rounded-[15px] bg-blue-50 text-brand-600"><MessageCircleMore className="h-[21px] w-[21px]" /></span><span><strong className="block text-[15px] font-black tracking-[-.015em] text-slate-900">Campaign Copilot</strong><small className="mt-1 block text-[11.5px] leading-[1.5] text-slate-500">Bạn dẫn lối, Agent mở rộng từng quyết định.</small></span><ArrowRight className="h-[18px] w-[18px] text-brand-600 max-sm:hidden" /></button>
              <button type="button" disabled={createDisabled} onClick={() => onCreate('autopilot')} className="grid min-h-[92px] grid-cols-[46px_minmax(0,1fr)_auto] items-center gap-3 rounded-[20px] border border-violet-200 bg-gradient-to-br from-white to-violet-50 p-4 text-left shadow-[0_16px_34px_rgba(109,40,217,.08)] transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-[0_22px_44px_rgba(109,40,217,.14)] disabled:cursor-not-allowed disabled:opacity-50"><span className="flex h-[46px] w-[46px] items-center justify-center rounded-[15px] bg-violet-100 text-violet-700"><Sparkles className="h-[21px] w-[21px]" /></span><span><strong className="block text-[15px] font-black tracking-[-.015em] text-slate-900">Campaign Autopilot</strong><small className="mt-1 block text-[11.5px] leading-[1.5] text-slate-500">Trao brief, Agent tự điều phối đến checkpoint.</small></span><ArrowRight className="h-[18px] w-[18px] text-violet-700 max-sm:hidden" /></button>
            </div>
          </div>
          {createError && <p className="relative mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-800">{createError}</p>}
          <div className="relative mt-[30px] grid grid-cols-3 gap-2.5 border-t border-slate-200 pt-[22px]" aria-label="Tổng quan campaign"><div className="min-w-0 px-1"><strong className="block text-[21px] font-black tracking-[-.04em] text-[#071226]">{draftCount}</strong><span className="mt-1 block text-[11px] leading-4 text-slate-500">Bản nháp đang được xây dựng</span></div><div className="min-w-0 px-1"><strong className="block text-[21px] font-black tracking-[-.04em] text-amber-700">{reviewCount}</strong><span className="mt-1 block text-[11px] leading-4 text-slate-500">Quyết định đang chờ bạn</span></div><div className="min-w-0 px-1"><strong className="block text-[21px] font-black tracking-[-.04em] text-emerald-700">{liveCount}</strong><span className="mt-1 block text-[11px] leading-4 text-slate-500">Campaign đang vận hành</span></div></div>
        </section>

        <section className="mt-7" aria-labelledby="workspace-heading">
          <div className="flex flex-wrap items-end gap-4"><div className="min-w-[220px] flex-1"><p className="text-[10px] font-black uppercase tracking-[.16em] text-brand-600">Campaign workspace</p><h2 id="workspace-heading" className="mt-1 text-[clamp(24px,3vw,34px)] font-black tracking-[-.04em] text-[#071226]">Hành trình của bạn</h2><p className="mt-1.5 text-[12.5px] text-slate-500">{active.length} đang hoạt động · {archived.length} đã lưu trữ</p></div><div className="ml-auto flex flex-wrap items-center gap-2.5 max-md:w-full"><label className="flex h-[42px] min-w-[220px] items-center gap-2 rounded-xl border border-slate-300 bg-white/80 px-3 max-md:order-first max-md:w-full"><Search className="h-4 w-4 shrink-0 text-slate-500" /><input value={query} onChange={event => setQuery(event.target.value)} className="min-w-0 flex-1 bg-transparent text-[12.5px] text-slate-900 outline-none" placeholder="Tìm campaign…" aria-label="Tìm campaign" /></label><div className="inline-flex gap-1 rounded-xl bg-slate-200 p-1 max-md:w-full" role="tablist" aria-label="Lọc campaign"><button type="button" onClick={() => setTab('active')} className={`h-[34px] rounded-[9px] px-3 text-[11.5px] font-black max-md:flex-1 ${tab === 'active' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500'}`} role="tab" aria-selected={tab === 'active'}>Đang hoạt động · {active.length}</button><button type="button" onClick={() => setTab('archived')} className={`h-[34px] rounded-[9px] px-3 text-[11.5px] font-black max-md:flex-1 ${tab === 'archived' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500'}`} role="tab" aria-selected={tab === 'archived'}>Lưu trữ · {archived.length}</button></div></div></div>

          {loading && <div className="mt-6 flex items-center justify-center gap-2 rounded-2xl border border-white/80 bg-white/70 py-20 text-sm text-slate-500"><Loader2 className="h-5 w-5 animate-spin" /> Đang tải campaign…</div>}
          {!loading && error && <div className="mt-6 rounded-2xl border border-red-200 bg-white p-6 text-center text-sm text-red-700 shadow-sm"><strong>Không tải được danh sách campaign.</strong><p className="mt-1">{error}</p><button type="button" onClick={onRefresh} className="mt-4 rounded-xl bg-red-600 px-4 py-2.5 text-xs font-black text-white">Tải lại danh sách</button></div>}
          {!loading && !error && !hasVisibleRows && <div className="mt-6 rounded-[24px] border border-dashed border-slate-300 bg-white/60 px-6 py-14 text-center"><div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[18px] bg-blue-50 text-brand-600"><Zap className="h-7 w-7" /></div><h2 className="mt-4 text-lg font-black text-slate-900">{query ? 'Không tìm thấy campaign' : tab === 'archived' ? 'Chưa có campaign lưu trữ' : 'Campaign đầu tiên bắt đầu từ đây'}</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{query ? 'Thử một tên campaign, brand hoặc mã campaign khác.' : 'Chọn Copilot hoặc Autopilot ở phía trên. Campaign sẽ xuất hiện tại workspace ngay từ khi còn là bản nháp.'}</p></div>}
          {!loading && !error && hasVisibleRows && groups.map(group => <CampaignGroup key={group.id} definition={group} page={pages[group.id] || 0} pageSize={pageSize} direction={pageDirections[group.id] || 'next'} onPageChange={changePage} cardProps={cardProps} />)}
          {campaigns.length > 0 && <div className="mt-9 flex flex-wrap items-center gap-2 border-t border-slate-300/80 pt-[18px]"><p className="min-w-[200px] flex-1 text-[11.5px] text-slate-500">Bạn có thể lưu trữ campaign để dọn workspace. Xóa không tác động order đã chạy trên ad server.</p><button type="button" onClick={onDeleteAll} className="h-[34px] rounded-[10px] border border-red-200 bg-white/75 px-3 text-[11.5px] font-black text-red-600 hover:bg-red-50">Xóa toàn bộ lịch sử làm việc…</button></div>}
        </section>
      </div>
      {campaigns.length > 0 && <ZaloContinuityNudge identity={identity} onLogin={onLogin} onLinkZalo={onLinkZalo} onOpenZaloOA={onOpenZaloOA} />}
    </main>
  )
}
