import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft, BarChart3, Bot, ChevronRight, ClipboardList, Download, History,
  Image, Layers3, Mail,
  RefreshCw, Settings2, ShieldCheck, Sparkles, Target, Wallet,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'
import EmailStep from '@/steps/EmailStep'
import ReportStep from '@/steps/ReportStep'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000'

const money = value => Number.isFinite(Number(value))
  ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value))
  : '—'

const dateLabel = value => {
  if (!value) return 'Chưa xác định'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString('vi-VN')
}

const statusLabel = lifecycle => ({ active: 'Đang vận hành', paused: 'Tạm dừng', completed: 'Hoàn tất' }[lifecycle] || 'Đã tạo campaign')

const navItems = [
  ['overview', 'Tổng quan', ClipboardList],
  ['setup', 'Campaign setup', Settings2],
  ['reports', 'Báo cáo', BarChart3],
  ['evaluation', 'Live Evaluation', RefreshCw],
]

function Metric({ icon: Icon, label, value, detail, tone = 'blue' }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700', emerald: 'bg-emerald-50 text-emerald-700',
    violet: 'bg-violet-50 text-violet-700', amber: 'bg-amber-50 text-amber-700',
  }
  return <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}><Icon className="h-5 w-5" /></span>
    <p className="mt-4 text-[10px] font-black uppercase tracking-[.14em] text-slate-400">{label}</p>
    <p className="mt-1 text-xl font-black text-slate-950">{value}</p>
    {detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}
  </div>
}

function EmptyList({ icon: Icon, children }) {
  return <div className="flex items-center gap-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-500"><Icon className="h-5 w-5 shrink-0 text-slate-400" />{children}</div>
}

function PreviewList({ title, icon: Icon, items, count, empty }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-start justify-between gap-3"><div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-700"><Icon className="h-4 w-4" /></span><div><h3 className="font-black text-slate-900">{title}</h3><p className="text-xs text-slate-500">{count ?? 0} mục thuộc campaign</p></div></div></div>
    <div className="mt-4 space-y-2">
      {items?.length ? items.map(item => <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2.5"><div className="min-w-0"><p className="truncate text-xs font-bold text-slate-800">{item.label}</p>{item.detail && <p className="truncate text-[11px] text-slate-500">{item.detail}</p>}</div><ChevronRight className="h-4 w-4 shrink-0 text-slate-300" /></div>) : <EmptyList icon={Icon}>{empty}</EmptyList>}
    </div>
  </section>
}

function CampaignAgent({ campaign, onOpenHistory }) {
  const hasHistory = Boolean(campaign.routes?.conversation)
  return <aside className="min-h-0 border-t border-slate-200 bg-white lg:sticky lg:top-0 lg:h-[calc(100vh-60px)] lg:border-l lg:border-t-0">
    <div className="flex h-full min-h-[390px] flex-col p-4">
      <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-700 shadow-lg shadow-violet-200"><Sparkles className="h-5 w-5 text-white" /></span><div><p className="text-sm font-black text-slate-950">Campaign Agent</p><p className="text-[11px] text-slate-500">Ngữ cảnh từ campaign hiện tại</p></div></div>
      <div className="mt-5 rounded-2xl border border-violet-100 bg-gradient-to-br from-violet-50 to-indigo-50 p-4"><p className="text-xs font-bold leading-5 text-violet-900">Campaign đã hoàn tất flow tạo lập. Lịch sử được giữ ở chế độ chỉ đọc để không làm thay đổi campaign truth.</p></div>
      <div className="mt-5 space-y-2"><p className="text-[10px] font-black uppercase tracking-[.14em] text-slate-400">Bạn có thể xem lại</p>{['Brief và quyết định đã duyệt', 'Placement, creative và report', 'Các bước tạo lập trong lịch sử'].map((item, index) => <div key={item} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5"><span className="text-xs font-black text-violet-600">0{index + 1}</span><span className="text-xs font-semibold text-slate-700">{item}</span></div>)}</div>
      <div className="mt-auto pt-5"><p className="mb-3 text-[11px] leading-5 text-slate-500">Campaign Agent chuyên biệt chưa có API chat riêng. Mở lịch sử là cách duy nhất để đặt câu hỏi trên ngữ cảnh campaign thật.</p>{hasHistory && <button type="button" onClick={() => onOpenHistory(campaign)} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#10284f] px-4 py-3 text-xs font-black text-white transition hover:bg-[#0b1f40]"><History className="h-4 w-4" /> Mở flow đã hoàn tất</button>}</div>
    </div>
  </aside>
}

function EvaluationPanel() {
  const [level, setLevel] = useState('standard')
  const levels = [['light', 'Light', 'Theo dõi snapshot định kỳ'], ['standard', 'Standard', 'Tổng hợp tín hiệu và đề xuất'], ['deep', 'Deep', 'Ưu tiên phân tích sâu hơn']]
  return <div className="space-y-5">
    <section className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-5"><div className="flex gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-600"><RefreshCw className="h-5 w-5 text-white" /></span><div><p className="text-xs font-black uppercase tracking-[.14em] text-violet-700">Live Evaluation</p><h2 className="mt-1 text-xl font-black text-slate-950">Thiết kế điều phối evaluation</h2><p className="mt-2 text-sm leading-6 text-slate-600">Bề mặt điều khiển đã sẵn sàng cho demo; scheduler và API thực thi evaluation chưa được nối. Vì vậy trang này không hiển thị score hoặc insight được đo lường.</p></div></div></section>
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-black text-slate-950">Mức theo dõi dự kiến</h3><div className="mt-4 grid gap-3 sm:grid-cols-3">{levels.map(([value, name, description]) => <button key={value} type="button" onClick={() => setLevel(value)} className={`rounded-xl border p-4 text-left transition ${level === value ? 'border-violet-500 bg-violet-50 shadow-sm' : 'border-slate-200 hover:border-violet-200'}`}><p className="text-sm font-black text-slate-900">{name}</p><p className="mt-1 text-xs leading-5 text-slate-500">{description}</p></button>)}</div><p className="mt-4 text-xs text-amber-700">Prototype interaction only — thay đổi này chưa được lưu và không kích hoạt worker.</p></section>
  </div>
}

export default function CampaignManagement({ campaign, loading, onBack, onOpenHistory }) {
  const [tab, setTab] = useState('overview')
  const [mobilePane, setMobilePane] = useState('campaign')
  const [emailOpen, setEmailOpen] = useState(false)
  const [reportStatus, setReportStatus] = useState(null)
  const [reportStatusError, setReportStatusError] = useState('')
  const order = campaign?.order || {}
  const campaignId = campaign?.campaign_id || order?.id || ''
  const mode = campaign?.experience_mode === 'autopilot' ? 'Autopilot' : 'Copilot'
  const reportReady = Boolean(reportStatus?.ready || reportStatus?.status === 'ready' || reportStatus?.hasReport)

  useEffect(() => {
    if (!campaignId) return undefined
    let active = true
    AgentAPI.getReportStatus(campaignId).then(data => { if (active) setReportStatus(data || {}) }).catch(() => { if (active) setReportStatusError('Không thể kiểm tra trạng thái report lúc này.') })
    return () => { active = false }
  }, [campaignId])

  const reportData = useMemo(() => ({ campaignId }), [campaignId])
  const reportForm = useMemo(() => ({ brief: { objective: order.objective || 'awareness' }, report: { campaignId } }), [campaignId, order.objective])

  if (loading) return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">Đang tải campaign…</div>
  if (!campaign) return <div className="flex min-h-screen items-center justify-center bg-slate-50 p-5"><div className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm"><h1 className="font-black text-slate-900">Không tìm thấy campaign</h1><p className="mt-2 text-sm text-slate-500">Campaign không tồn tại hoặc không thuộc tài khoản/thiết bị này.</p><button type="button" onClick={onBack} className="mt-4 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-black text-white">Về danh sách campaign</button></div></div>

  const renderTab = () => {
    if (tab === 'setup') return <div className="grid gap-5 xl:grid-cols-2"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-[10px] font-black uppercase tracking-[.14em] text-brand-600">Campaign truth</p><h2 className="mt-1 text-xl font-black text-slate-950">Thiết lập đã duyệt</h2><dl className="mt-4 divide-y divide-slate-100 text-sm">{[['Mục tiêu', order.objective || 'Chưa xác định'], ['Ngân sách', money(order.budget)], ['Ngân sách ngày', money(order.daily_budget)], ['Thời gian', `${dateLabel(order.start_date)} — ${dateLabel(order.end_date)}`], ['Trạng thái order', order.status || 'Chưa có dữ liệu']].map(([label, value]) => <div key={label} className="grid gap-2 py-3 sm:grid-cols-[140px_1fr]"><dt className="text-slate-500">{label}</dt><dd className="font-bold text-slate-900">{value}</dd></div>)}</dl></section><div className="space-y-5"><PreviewList title="Placement" icon={Target} items={order.placement_preview} count={order.placement_count} empty="API hiện chỉ có số lượng placement; tên zone sẽ xuất hiện khi order cung cấp dữ liệu." /><PreviewList title="Creative" icon={Image} items={order.creative_preview} count={order.creative_count} empty="API hiện chỉ có số lượng creative; asset preview sẽ xuất hiện khi order cung cấp dữ liệu." /></div></div>
    if (tab === 'reports') return <div className="space-y-5"><section className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between"><div><p className="text-[10px] font-black uppercase tracking-[.14em] text-brand-600">Six-report workflow</p><h2 className="mt-1 text-xl font-black text-slate-950">Report & evidence</h2><p className="mt-1 text-xs text-slate-500">Dùng đúng report service và data contract của campaign hiện tại.</p></div><div className="flex gap-2"><a href={`${BACKEND_URL}/api/reports/export/${encodeURIComponent(campaignId)}/pdf`} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 text-xs font-black text-slate-700 hover:bg-slate-50"><Download className="h-4 w-4" /> PDF</a><button type="button" onClick={() => setEmailOpen(true)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-3 py-2.5 text-xs font-black text-white hover:bg-brand-700"><Mail className="h-4 w-4" /> Thiết lập email</button></div></section>{reportStatusError && <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">{reportStatusError}</p>}<ReportStep data={reportData} formState={reportForm} isDone={reportReady} onChange={() => {}} onSendChat={() => {}} onRetry={() => {}} /></div>
    if (tab === 'evaluation') return <EvaluationPanel />
    return <div className="space-y-5"><section className="rounded-2xl bg-gradient-to-br from-[#071d41] via-[#0b356d] to-[#0b5a9c] p-6 text-white shadow-[0_22px_54px_rgba(7,29,65,.23)]"><div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between"><div><div className="flex flex-wrap gap-2"><span className="rounded-full border border-emerald-300/30 bg-emerald-400/15 px-3 py-1 text-[10px] font-black tracking-[.14em] text-emerald-100">{statusLabel(campaign.lifecycle).toUpperCase()}</span><span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[10px] font-black">{mode.toUpperCase()}</span></div><h1 className="mt-4 text-2xl font-black tracking-[-.035em] sm:text-3xl">{campaign.title}</h1><p className="mt-2 text-sm text-blue-100">{campaignId} · {order.order_count || 1} order được liên kết</p></div>{campaign.routes?.conversation && <button type="button" onClick={() => onOpenHistory(campaign)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-xs font-black text-[#10284f]"><History className="h-4 w-4" /> Xem flow chỉ đọc</button>}</div></section><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric icon={Wallet} label="Ngân sách" value={money(order.budget)} detail={order.daily_budget ? `${money(order.daily_budget)} / ngày` : 'Ngân sách campaign'} /><Metric icon={Layers3} label="Placement" value={order.placement_count ?? '—'} detail="Ad zone đã gán" tone="violet" /><Metric icon={Image} label="Creative" value={order.creative_count ?? '—'} detail="Creative đã gán" tone="emerald" /><Metric icon={ShieldCheck} label="Cảnh báo" value={order.warning_count ?? 0} detail="Từ campaign directory" tone="amber" /></div><div className="grid gap-5 xl:grid-cols-[1.25fr_.75fr]"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-[10px] font-black uppercase tracking-[.14em] text-brand-600">Campaign handoff</p><h2 className="mt-1 text-xl font-black text-slate-950">Từ flow tạo lập sang vận hành</h2><p className="mt-3 text-sm leading-6 text-slate-600">Campaign config, placement và creative được đọc từ owned order. Flow đã hoàn tất được mở ở chế độ chỉ đọc để giữ nguyên quyết định đã duyệt.</p><div className="mt-5 flex flex-wrap gap-2">{campaign.routes?.conversation && <button type="button" onClick={() => onOpenHistory(campaign)} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-black text-white"><History className="h-4 w-4" /> Lịch sử tạo campaign</button>}<button type="button" onClick={() => setTab('setup')} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-black text-slate-700"><Settings2 className="h-4 w-4" /> Xem campaign setup</button></div></section><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-[10px] font-black uppercase tracking-[.14em] text-violet-600">Latest report</p><h2 className="mt-1 text-xl font-black text-slate-950">{reportReady ? 'Report sẵn sàng' : 'Đang chờ report'}</h2><p className="mt-3 text-sm leading-6 text-slate-500">{reportReady ? 'Mở 6 góc nhìn report, evidence contract và file PDF từ report service.' : 'Report sẽ hiển thị ở đây khi report service hoàn tất dữ liệu cho campaign.'}</p><button type="button" onClick={() => setTab('reports')} className="mt-5 inline-flex items-center gap-2 text-xs font-black text-brand-700">Mở report <ChevronRight className="h-4 w-4" /></button></section></div></div>
  }

  return <main className="h-full overflow-x-hidden overflow-y-auto overscroll-contain bg-[#eef2f8] text-slate-900">
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur"><div className="mx-auto flex h-[60px] max-w-[1560px] items-center gap-3 px-4 sm:px-6"><button type="button" onClick={onBack} className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50" aria-label="Về danh sách campaign"><ArrowLeft className="h-4 w-4" /></button><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#10284f]"><Bot className="h-4 w-4 text-white" /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-black text-slate-950">Campaign Management</p><p className="truncate text-[11px] text-slate-500">{campaign.title} · {campaignId}</p></div><div className="hidden items-center gap-2 sm:flex"><span className="rounded-full bg-emerald-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-[.12em] text-emerald-700">{statusLabel(campaign.lifecycle)}</span><span className="rounded-full bg-slate-100 px-3 py-1.5 text-[10px] font-black text-slate-600">{mode}</span></div></div></header>
    <div className="mx-auto max-w-[1560px] lg:grid lg:grid-cols-[210px_minmax(0,1fr)_340px]">
      <nav className="hidden border-r border-slate-200 bg-[#10284f] px-3 py-5 lg:block lg:min-h-[calc(100vh-60px)]" aria-label="Campaign sections"><p className="px-3 text-[10px] font-black uppercase tracking-[.15em] text-blue-200">Campaign space</p><div className="mt-3 space-y-1">{navItems.map(([value, label, Icon]) => <button key={value} type="button" onClick={() => setTab(value)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-xs font-bold transition ${tab === value ? 'bg-white text-[#10284f] shadow-sm' : 'text-blue-100 hover:bg-white/10 hover:text-white'}`}><Icon className="h-4 w-4" />{label}{value === 'reports' && <span className="ml-auto rounded-full bg-blue-100 px-1.5 py-0.5 text-[9px] font-black text-blue-700">6</span>}</button>)}</div><div className="mt-7 rounded-xl border border-white/10 bg-white/5 p-3 text-[11px] leading-5 text-blue-100"><p className="font-black text-white">Read-only creation flow</p><p className="mt-1">Các quyết định đã duyệt vẫn truy vết được từ lịch sử.</p></div></nav>
      <section className={`${mobilePane === 'agent' ? 'hidden lg:block' : 'block'} min-w-0 p-4 sm:p-6`}>{renderTab()}</section>
      <div className={`${mobilePane === 'campaign' ? 'hidden lg:block' : 'block'} min-w-0`}><CampaignAgent campaign={campaign} onOpenHistory={onOpenHistory} /></div>
    </div>
    <div className="fixed inset-x-4 bottom-4 z-40 flex rounded-xl border border-slate-200 bg-white p-1 shadow-xl lg:hidden"><button type="button" onClick={() => setMobilePane('campaign')} className={`flex-1 rounded-lg px-3 py-2 text-xs font-black ${mobilePane === 'campaign' ? 'bg-[#10284f] text-white' : 'text-slate-500'}`}>Campaign</button><button type="button" onClick={() => setMobilePane('agent')} className={`flex-1 rounded-lg px-3 py-2 text-xs font-black ${mobilePane === 'agent' ? 'bg-violet-600 text-white' : 'text-slate-500'}`}>Campaign Agent</button></div>
    {emailOpen && <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/45 p-4"><div className="mx-auto my-6 max-w-xl rounded-2xl bg-white p-5 shadow-2xl"><div className="mb-5 flex items-center justify-between"><div><p className="text-sm font-black text-slate-950">Thiết lập email report</p><p className="text-xs text-slate-500">Campaign {campaignId}</p></div><button type="button" onClick={() => setEmailOpen(false)} className="rounded-lg px-3 py-2 text-xs font-bold text-slate-500 hover:bg-slate-100">Đóng</button></div><EmailStep brief={{ brand: campaign.title, objective: order.objective || 'awareness' }} zones={[]} selectedZoneIds={[]} audiences={[]} data={{ campaignId }} formState={reportForm} isDone={false} onChange={() => {}} /></div></div>}
  </main>
}
