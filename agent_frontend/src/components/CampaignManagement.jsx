import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft, BarChart3, Bot, ChevronRight, ClipboardList, Download, ExternalLink,
  Eye, FileClock, History, Image, Layers3, Mail, MessageCircleMore, Minimize2,
  RefreshCw, Save, Send, Settings2, ShieldCheck, Sparkles, Target, Wallet, X,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'
import EmailStep from '@/steps/EmailStep'
import ReportStep from '@/steps/ReportStep'
import LiveEvaluationPanel, { analyticsUrl } from './CampaignEvaluationWorkspace'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000'

const money = value => Number.isFinite(Number(value))
  ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value))
  : '—'

const dateLabel = value => {
  if (!value) return 'Chưa xác định'
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString('vi-VN')
}

const statusLabel = lifecycle => ({
  active: 'Đang vận hành', paused: 'Tạm dừng', completed: 'Hoàn tất',
  scheduled: 'Sắp chạy', failed: 'Có lỗi', archived: 'Lưu trữ',
}[lifecycle] || 'Đã tạo campaign')

const navItems = [
  ['overview', 'Tổng quan', ClipboardList],
  ['setup', 'Campaign setup', Settings2],
  ['reports', 'Báo cáo', BarChart3],
  ['evaluation', 'Live Evaluation', RefreshCw],
]

function derivedDaily(config, fallback) {
  if (Number(config?.daily) > 0) return Number(config.daily)
  const budget = Number(config?.budget)
  const start = new Date(`${String(config?.startDate || '').slice(0, 10)}T00:00:00`)
  const end = new Date(`${String(config?.endDate || '').slice(0, 10)}T00:00:00`)
  const days = Math.floor((end - start) / 86400000) + 1
  return budget > 0 && days > 0 ? Math.round(budget / days) : fallback
}

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

function CurrentConfig({ order, onEdit }) {
  const rows = [
    ['Mục tiêu', order.objective || 'Chưa xác định'],
    ['Tổng ngân sách', money(order.budget)],
    ['Ngân sách ngày', money(order.daily_budget), order.daily_budget_source === 'derived' ? 'Ước tính từ tổng ngân sách / số ngày' : 'Hạn mức đã cấu hình'],
    ['Thời gian', `${dateLabel(order.start_date)} — ${dateLabel(order.end_date)}`],
    ['Trạng thái hiệu lực', statusLabel(order.effective_status)],
    ['Trạng thái nguồn', order.status || 'Chưa có dữ liệu', 'Giữ nguyên từ order để đối chiếu/audit'],
  ]
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-[10px] font-black uppercase tracking-[.14em] text-brand-600">Campaign truth</p><h2 className="mt-1 text-xl font-black text-slate-950">Cấu hình hiện tại</h2><p className="mt-1 text-xs text-slate-500">Cấu hình đang có hiệu lực; mọi lần sửa được lưu thành revision.</p></div>
      <button type="button" onClick={onEdit} className="inline-flex items-center gap-2 rounded-xl bg-[#10284f] px-4 py-2.5 text-xs font-black text-white"><Settings2 className="h-4 w-4" /> Xem & chỉnh sửa</button>
    </div>
    <dl className="mt-5 divide-y divide-slate-100">
      {rows.map(([label, value, help]) => <div key={label} className="grid gap-1 py-3 text-sm sm:grid-cols-[180px_1fr]"><dt className="text-slate-500">{label}</dt><dd className="font-bold text-slate-900">{value}{help && <span className="mt-1 block text-[11px] font-normal text-slate-400">{help}</span>}</dd></div>)}
    </dl>
  </section>
}

function AssetList({ title, icon: Icon, items, count, kind, onPreview }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700"><Icon className="h-5 w-5" /></span><div><h3 className="font-black text-slate-900">{title}</h3><p className="text-xs text-slate-500">{count ?? 0} mục thuộc campaign</p></div></div>
    <div className="mt-4 space-y-2">
      {items?.length ? items.map(item => <div key={item.id} className="flex min-w-0 items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3">
        {kind === 'creative' && item.url ? <button type="button" onClick={() => onPreview(item)} className="h-14 w-20 shrink-0 overflow-hidden rounded-lg border border-slate-200 bg-white"><img src={item.url} alt={item.label} className="h-full w-full object-cover" /></button> : <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-slate-400"><Icon className="h-4 w-4" /></span>}
        <div className="min-w-0 flex-1"><p className="truncate text-sm font-bold text-slate-900">{item.label}</p><p className="mt-0.5 truncate text-[11px] text-slate-500">{item.detail || (item.url ? 'Có liên kết' : 'Chưa có liên kết/asset preview')}</p></div>
        {item.url && kind === 'placement' && <a href={item.url} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-black text-brand-700">Tới site <ExternalLink className="h-3.5 w-3.5" /></a>}
        {item.url && kind === 'creative' && <button type="button" onClick={() => onPreview(item)} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-black text-brand-700"><Eye className="h-3.5 w-3.5" /> Xem ảnh</button>}
      </div>) : <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-500">Campaign cũ chưa lưu đủ metadata {kind === 'creative' ? 'creative' : 'placement'} để mở preview.</div>}
    </div>
  </section>
}

function ConfigEditor({ campaignId, configData, onReload }) {
  const config = configData?.config || {}
  const [form, setForm] = useState({})
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [retryRequestId, setRetryRequestId] = useState('')

  useEffect(() => {
    setForm({
      objective: config.objective || 'awareness', budget: config.budget ?? '',
      daily: Number(config.daily) > 0 ? config.daily : '',
      startDate: String(config.startDate || '').slice(0, 10),
      endDate: String(config.endDate || '').slice(0, 10),
    })
  }, [configData?.revision, config.objective, config.budget, config.daily, config.startDate, config.endDate])

  const change = (key, value) => {
    setRetryRequestId('')
    setForm(current => ({ ...current, [key]: value }))
  }
  const save = async event => {
    event.preventDefault(); setBusy(true); setError(''); setSaved('')
    const patch = {
      objective: form.objective, budget: Number(form.budget), daily: Number(form.daily || 0),
      startDate: form.startDate, endDate: form.endDate,
    }
    const requestId = retryRequestId || globalThis.crypto?.randomUUID?.() || `campaign-config-${Date.now()}`
    setRetryRequestId(requestId)
    try {
      const result = await AgentAPI.updateCampaignConfig(campaignId, configData?.revision || 0, patch, note, requestId)
      setSaved(`Đã lưu revision ${result.revision.revision}.`); setNote(''); setRetryRequestId(''); await onReload()
    } catch (reason) { setError(reason.message || 'Không thể lưu config.') } finally { setBusy(false) }
  }

  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div><p className="text-[10px] font-black uppercase tracking-[.14em] text-brand-600">Revision {configData?.revision || 0}</p><h2 className="mt-1 text-xl font-black text-slate-950">Chỉnh sửa cấu hình vận hành</h2><p className="mt-1 text-xs leading-5 text-slate-500">Các trường an toàn được sửa tại đây. Placement/creative dùng viewer riêng và chưa nhận giá trị text tự do.</p></div>
    <form onSubmit={save} className="mt-5 grid gap-4">
      <label className="text-xs font-bold text-slate-700">Mục tiêu<select value={form.objective || ''} onChange={event => change('objective', event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm font-semibold outline-none focus:border-brand-500"><option value="awareness">Awareness</option><option value="consideration">Consideration</option><option value="conversion">Conversion</option><option value="retention">Retention</option></select></label>
      <label className="text-xs font-bold text-slate-700">Tổng ngân sách<input required min="1" type="number" value={form.budget ?? ''} onChange={event => change('budget', event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border border-slate-300 px-3 text-sm font-semibold outline-none focus:border-brand-500" /></label>
      <label className="text-xs font-bold text-slate-700">Ngày bắt đầu<input required type="date" value={form.startDate || ''} onChange={event => change('startDate', event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border border-slate-300 px-3 text-sm font-semibold outline-none focus:border-brand-500" /></label>
      <label className="text-xs font-bold text-slate-700">Ngày kết thúc<input required type="date" value={form.endDate || ''} onChange={event => change('endDate', event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border border-slate-300 px-3 text-sm font-semibold outline-none focus:border-brand-500" /></label>
      <label className="text-xs font-bold text-slate-700">Ngân sách ngày (tùy chọn)<input min="0" type="number" value={form.daily ?? ''} onChange={event => change('daily', event.target.value)} placeholder="Để trống: tự chia tổng ngân sách theo số ngày" className="mt-1.5 h-11 w-full rounded-xl border border-slate-300 px-3 text-sm font-semibold outline-none focus:border-brand-500" /><span className="mt-1 block text-[11px] font-normal text-slate-500">Để trống sẽ hiển thị mức ước tính; không còn hiện 0 đ gây hiểu nhầm.</span></label>
      <label className="text-xs font-bold text-slate-700">Ghi chú revision<input value={note} onChange={event => { setRetryRequestId(''); setNote(event.target.value) }} maxLength={500} placeholder="Ví dụ: điều chỉnh ngân sách sau review tuần 1" className="mt-1.5 h-11 w-full rounded-xl border border-slate-300 px-3 text-sm outline-none focus:border-brand-500" /></label>
      {error && <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
      {saved && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{saved}</p>}
      <div><button disabled={busy} type="submit" className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-3 text-xs font-black text-white disabled:opacity-50"><Save className="h-4 w-4" /> {busy ? 'Đang lưu…' : 'Lưu thành revision mới'}</button></div>
    </form>
  </section>
}

function RevisionHistory({ rows = [] }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-700"><FileClock className="h-5 w-5" /></span><div><h3 className="font-black text-slate-900">Lịch sử revision</h3><p className="text-xs text-slate-500">Before/after diff bất biến của các lần chỉnh sửa.</p></div></div>
    <div className="mt-4 space-y-3">{rows.length ? rows.map(row => <details key={row.request_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3"><summary className="cursor-pointer text-xs font-black text-slate-800">Revision {row.revision} · {row.note || 'Không có ghi chú'}<span className="ml-2 font-normal text-slate-400">{row.completed_at ? new Date(row.completed_at).toLocaleString('vi-VN') : ''}</span></summary><div className="mt-3 space-y-2">{Object.entries(row.changes || {}).map(([key, values]) => <div key={key} className="grid gap-1 rounded-lg bg-white p-2 text-[11px] sm:grid-cols-[100px_1fr]"><strong>{key}</strong><span className="break-words text-slate-600">{String(values.before ?? '—')} → <b className="text-slate-900">{String(values.after ?? '—')}</b></span></div>)}</div></details>) : <p className="rounded-xl border border-dashed border-slate-200 p-4 text-xs text-slate-500">Chưa có lần chỉnh sửa nào. Order hiện tại là baseline revision 0.</p>}</div>
  </section>
}

function CampaignAgentBubble({ campaignId, title, onNavigate }) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState([{ role: 'assistant', text: `Hỏi mình về ${title}. Mình có thể giải thích campaign và dẫn bạn tới đúng trang, nhưng không sửa campaign trong chat.` }])
  const send = async value => {
    const clean = String(value || question).trim()
    if (!clean || busy) return
    setMessages(rows => [...rows, { role: 'user', text: clean }]); setQuestion(''); setBusy(true)
    try {
      const result = await AgentAPI.askCampaignAssistant(campaignId, clean)
      setMessages(rows => [...rows, { role: 'assistant', text: result.answer, target: result.target_tab, label: result.target_label }])
    } catch (error) { setMessages(rows => [...rows, { role: 'assistant', text: error.message || 'Mình chưa trả lời được lúc này.' }]) } finally { setBusy(false) }
  }
  if (!open) return <button type="button" onClick={() => setOpen(true)} className="campaign-agent-attention fixed bottom-5 right-5 z-40 flex h-14 items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-indigo-700 px-4 text-white shadow-[0_18px_48px_rgba(91,33,182,.35)]" aria-label="Hỏi Campaign Agent"><span className="relative"><MessageCircleMore className="h-6 w-6" /><i className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-violet-600 bg-emerald-400" /></span><span className="hidden text-xs font-black sm:block">Hỏi về campaign</span></button>
  return <aside className="fixed bottom-3 right-3 z-50 flex max-h-[min(520px,70vh)] w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl border border-violet-200 bg-white shadow-[0_26px_80px_rgba(30,41,90,.30)] sm:bottom-5 sm:right-5 sm:w-[min(380px,30vw)] sm:min-w-[310px]" aria-label="Campaign Agent chat">
    <header className="flex items-center gap-3 bg-gradient-to-r from-violet-600 to-indigo-700 p-3.5 text-white"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15"><Sparkles className="h-5 w-5" /></span><div className="min-w-0 flex-1"><p className="text-sm font-black">Campaign Agent</p><p className="truncate text-[10px] text-violet-100">Chỉ hỏi đáp & điều hướng · không mutation</p></div><button type="button" onClick={() => setOpen(false)} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10" aria-label="Thu nhỏ chat"><Minimize2 className="h-4 w-4" /></button></header>
    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-slate-50 p-3.5">{messages.map((message, index) => <div key={`${message.role}-${index}`} className={`max-w-[88%] rounded-2xl px-3 py-2.5 text-xs leading-5 ${message.role === 'user' ? 'ml-auto rounded-br-sm bg-brand-600 text-white' : 'rounded-bl-sm border border-slate-200 bg-white text-slate-700'}`}><p>{message.text}</p>{message.target && <button type="button" onClick={() => { onNavigate(message.target); setOpen(false) }} className="mt-2 inline-flex items-center gap-1 font-black text-brand-700">{message.label}<ChevronRight className="h-3.5 w-3.5" /></button>}</div>)}{busy && <div className="w-fit rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">Đang đọc campaign…</div>}</div>
    {messages.length === 1 && <div className="flex gap-1.5 overflow-x-auto border-t border-slate-100 px-3 py-2">{['Có incident nào?', 'Xem creative ở đâu?', 'Scenario Lab ở đâu?'].map(item => <button key={item} type="button" onClick={() => send(item)} className="shrink-0 rounded-full bg-violet-50 px-2.5 py-1.5 text-[10px] font-bold text-violet-700">{item}</button>)}</div>}
    <form onSubmit={event => { event.preventDefault(); send() }} className="flex gap-2 border-t border-slate-200 bg-white p-3"><input value={question} onChange={event => setQuestion(event.target.value)} placeholder="Hỏi về campaign này…" className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 text-xs outline-none focus:border-violet-500" /><button disabled={!question.trim() || busy} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-600 text-white disabled:opacity-40" aria-label="Gửi câu hỏi"><Send className="h-4 w-4" /></button></form>
  </aside>
}

export default function CampaignManagement({ campaign, loading, onBack, onOpenHistory }) {
  const [tab, setTab] = useState('overview')
  const [emailOpen, setEmailOpen] = useState(false)
  const [preview, setPreview] = useState(null)
  const [reportStatus, setReportStatus] = useState(null)
  const [reportStatusError, setReportStatusError] = useState('')
  const [evaluationSummary, setEvaluationSummary] = useState(null)
  const [configData, setConfigData] = useState(null)
  const [configError, setConfigError] = useState('')
  const order = campaign?.order || {}
  const campaignId = campaign?.campaign_id || order?.id || ''
  const mode = campaign?.experience_mode === 'autopilot' ? 'Autopilot' : 'Copilot'
  const reportReady = Boolean(reportStatus?.ready || reportStatus?.status === 'ready' || reportStatus?.hasReport)
  const sourceConfig = configData?.config
  const displayOrder = useMemo(() => ({
    ...order,
    objective: sourceConfig?.objective ?? order.objective,
    budget: sourceConfig?.budget ?? order.budget,
    daily_budget: sourceConfig ? derivedDaily(sourceConfig, order.daily_budget) : order.daily_budget,
    daily_budget_source: sourceConfig?.daily > 0 ? 'explicit' : order.daily_budget_source || 'derived',
    start_date: sourceConfig?.startDate ?? order.start_date,
    end_date: sourceConfig?.endDate ?? order.end_date,
    status: sourceConfig?.status ?? order.status,
    effective_status: campaign?.lifecycle,
  }), [campaign?.lifecycle, order, sourceConfig])

  const loadConfig = async () => {
    if (!campaignId) return
    try { setConfigData(await AgentAPI.getCampaignConfig(campaignId)); setConfigError('') }
    catch (error) { setConfigError(error.message || 'Không thể tải config.') }
  }

  useEffect(() => {
    if (!campaignId) return undefined
    let active = true
    AgentAPI.getReportStatus(campaignId).then(data => { if (active) setReportStatus(data || {}) }).catch(() => { if (active) setReportStatusError('Không thể kiểm tra trạng thái report lúc này.') })
    loadConfig()
    return () => { active = false }
  }, [campaignId])

  useEffect(() => {
    if (!campaignId) return undefined
    let active = true
    const refresh = () => AgentAPI.getCampaignEvaluation(campaignId).then(data => { if (active) setEvaluationSummary(data.summary) }).catch(() => { if (active) setEvaluationSummary(null) })
    refresh(); window.addEventListener('focus', refresh)
    return () => { active = false; window.removeEventListener('focus', refresh) }
  }, [campaignId])

  const reportData = useMemo(() => ({ campaignId }), [campaignId])
  const reportForm = useMemo(() => ({ brief: { objective: displayOrder.objective || 'awareness' }, report: { campaignId } }), [campaignId, displayOrder.objective])

  if (loading) return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">Đang tải campaign…</div>
  if (!campaign) return <div className="flex min-h-screen items-center justify-center bg-slate-50 p-5"><div className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm"><h1 className="font-black text-slate-900">Không tìm thấy campaign</h1><p className="mt-2 text-sm text-slate-500">Campaign không tồn tại hoặc không thuộc tài khoản/thiết bị này.</p><button type="button" onClick={onBack} className="mt-4 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-black text-white">Về danh sách campaign</button></div></div>

  const renderOverview = () => <div className="space-y-5">
    <section className="rounded-2xl bg-gradient-to-br from-[#071d41] via-[#0b356d] to-[#0b5a9c] p-6 text-white shadow-[0_22px_54px_rgba(7,29,65,.23)]"><div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between"><div><div className="flex flex-wrap gap-2"><span className="rounded-full border border-emerald-300/30 bg-emerald-400/15 px-3 py-1 text-[10px] font-black tracking-[.14em] text-emerald-100">{statusLabel(campaign.lifecycle).toUpperCase()}</span><span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[10px] font-black">{mode.toUpperCase()}</span></div><h1 className="mt-4 text-2xl font-black tracking-[-.035em] sm:text-3xl">{campaign.title}</h1><p className="mt-2 text-sm text-blue-100">{campaignId} · {order.order_count || 1} order được liên kết</p></div>{campaign.routes?.conversation && <button type="button" onClick={() => onOpenHistory(campaign)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-xs font-black text-[#10284f]"><History className="h-4 w-4" /> Xem flow chỉ đọc</button>}</div></section>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric icon={Wallet} label="Ngân sách" value={money(displayOrder.budget)} detail={displayOrder.daily_budget ? `${money(displayOrder.daily_budget)} / ngày${displayOrder.daily_budget_source === 'derived' ? ' (ước tính)' : ''}` : 'Ngân sách campaign'} /><Metric icon={Layers3} label="Placement" value={order.placement_count ?? '—'} detail="Ad zone đã gán" tone="violet" /><Metric icon={Image} label="Creative" value={order.creative_count ?? '—'} detail="Creative đã gán" tone="emerald" /><Metric icon={ShieldCheck} label="Cảnh báo" value={evaluationSummary?.open_count ?? order.warning_count ?? 0} detail="Incident đang mở" tone="amber" /></div>
    <CurrentConfig order={displayOrder} onEdit={() => setTab('setup')} />
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-[10px] font-black uppercase tracking-[.14em] text-violet-600">Latest report</p><h2 className="mt-1 text-xl font-black text-slate-950">{reportReady ? 'Report sẵn sàng' : 'Đang chờ report'}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{reportReady ? 'Mở 6 góc nhìn report, evidence contract và Scenario Lab của campaign hiện tại.' : 'Report sẽ hiển thị khi report service hoàn tất dữ liệu.'}</p><button type="button" onClick={() => setTab('reports')} className="mt-4 inline-flex items-center gap-2 text-xs font-black text-brand-700">Mở report <ChevronRight className="h-4 w-4" /></button></section>
  </div>

  const renderTab = () => {
    if (tab === 'setup') return <div className="space-y-5">{configError && <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">{configError}</p>}<ConfigEditor campaignId={campaignId} configData={configData} onReload={loadConfig} /><AssetList title="Placement" icon={Target} items={order.placement_preview} count={order.placement_count} kind="placement" onPreview={setPreview} /><AssetList title="Creative" icon={Image} items={order.creative_preview} count={order.creative_count} kind="creative" onPreview={setPreview} /><RevisionHistory rows={configData?.history} /></div>
    if (tab === 'reports') return <div className="space-y-5"><a className="inline-flex items-center gap-2 text-sm font-semibold text-blue-700 underline" href={analyticsUrl(campaignId)} target="_blank" rel="noreferrer">Giả lập tình huống trong Analytics <ExternalLink className="h-4 w-4" /></a><section className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between"><div><p className="text-[10px] font-black uppercase tracking-[.14em] text-brand-600">Six-report workflow</p><h2 className="mt-1 text-xl font-black text-slate-950">Report & evidence</h2><p className="mt-1 text-xs text-slate-500">Dùng đúng report service và data contract của campaign hiện tại.</p></div><div className="flex gap-2"><a href={`${BACKEND_URL}/api/reports/export/${encodeURIComponent(campaignId)}/pdf`} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 text-xs font-black text-slate-700 hover:bg-slate-50"><Download className="h-4 w-4" /> PDF</a><button type="button" onClick={() => setEmailOpen(true)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-3 py-2.5 text-xs font-black text-white hover:bg-brand-700"><Mail className="h-4 w-4" /> Thiết lập email</button></div></section>{reportStatusError && <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">{reportStatusError}</p>}<ReportStep data={reportData} formState={reportForm} isDone={reportReady} onChange={() => {}} onSendChat={() => {}} onRetry={() => {}} /></div>
    if (tab === 'evaluation') return <LiveEvaluationPanel key={campaignId} campaignId={campaignId} />
    return renderOverview()
  }

  return <main className="h-full overflow-x-hidden overflow-y-auto overscroll-contain bg-[#eef2f8] text-slate-900">
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur"><div className="mx-auto flex h-[60px] max-w-[1380px] items-center gap-3 px-4 sm:px-6"><button type="button" onClick={onBack} className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50" aria-label="Về danh sách campaign"><ArrowLeft className="h-4 w-4" /></button><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#10284f]"><Bot className="h-4 w-4 text-white" /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-black text-slate-950">Campaign Management</p><p className="truncate text-[11px] text-slate-500">{campaign.title} · {campaignId}</p></div><div className="hidden items-center gap-2 sm:flex"><span className="rounded-full bg-emerald-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-[.12em] text-emerald-700">{statusLabel(campaign.lifecycle)}</span><span className="rounded-full bg-slate-100 px-3 py-1.5 text-[10px] font-black text-slate-600">{mode}</span></div></div></header>
    <div className="border-b border-slate-200 bg-white px-3 py-2 lg:hidden"><div className="flex gap-1 overflow-x-auto">{navItems.map(([value, label, Icon]) => <button key={value} type="button" onClick={() => setTab(value)} className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-bold ${tab === value ? 'bg-[#10284f] text-white' : 'text-slate-600'}`}><Icon className="h-4 w-4" />{label}</button>)}</div></div>
    <div className="mx-auto max-w-[1380px] lg:grid lg:grid-cols-[210px_minmax(0,1fr)]">
      <nav className="hidden border-r border-slate-200 bg-[#10284f] px-3 py-5 lg:block lg:min-h-[calc(100vh-60px)]" aria-label="Campaign sections"><p className="px-3 text-[10px] font-black uppercase tracking-[.15em] text-blue-200">Campaign space</p><div className="mt-3 space-y-1">{navItems.map(([value, label, Icon]) => <button key={value} type="button" onClick={() => setTab(value)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-xs font-bold transition ${tab === value ? 'bg-white text-[#10284f] shadow-sm' : 'text-blue-100 hover:bg-white/10 hover:text-white'}`}><Icon className="h-4 w-4" />{label}{value === 'reports' && <span className="ml-auto rounded-full bg-blue-100 px-1.5 py-0.5 text-[9px] font-black text-blue-700">6</span>}</button>)}</div><div className="mt-7 rounded-xl border border-white/10 bg-white/5 p-3 text-[11px] leading-5 text-blue-100"><p className="font-black text-white">Revisioned campaign truth</p><p className="mt-1">Flow tạo lập vẫn chỉ đọc; thay đổi vận hành được lưu riêng theo revision.</p></div></nav>
      <section className="min-w-0 p-4 pb-24 sm:p-6 sm:pb-24">{tab === 'overview' && <section className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5"><div><h2 className="font-bold">Campaign health</h2><p className="mt-1 text-sm text-slate-600">{evaluationSummary ? evaluationSummary.open_count > 0 ? `${evaluationSummary.open_count} incident cần theo dõi` : evaluationSummary.status === 'healthy' ? 'Không còn tín hiệu cảnh báo ở lần đánh giá gần nhất' : 'Chưa có đánh giá hoàn tất' : 'Chưa tải được trạng thái Evaluation'}</p></div><button className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white" onClick={() => setTab('evaluation')}>Xem incident</button></section>}{renderTab()}</section>
    </div>
    <CampaignAgentBubble campaignId={campaignId} title={campaign.title} onNavigate={setTab} />
    {preview && <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/75 p-4" role="dialog" aria-modal="true" aria-label={`Creative ${preview.label}`}><div className="relative max-h-[92vh] max-w-5xl overflow-hidden rounded-2xl bg-white p-3 shadow-2xl"><button type="button" onClick={() => setPreview(null)} className="absolute right-4 top-4 z-10 flex h-9 w-9 items-center justify-center rounded-full bg-slate-950/70 text-white" aria-label="Đóng creative viewer"><X className="h-5 w-5" /></button><img src={preview.url} alt={preview.label} className="max-h-[80vh] max-w-full rounded-xl object-contain" /><div className="px-2 pb-1 pt-3"><p className="font-black text-slate-900">{preview.label}</p><p className="text-xs text-slate-500">{preview.detail || 'Creative asset'}</p></div></div></div>}
    {emailOpen && <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/45 p-4"><div className="mx-auto my-6 max-w-xl rounded-2xl bg-white p-5 shadow-2xl"><div className="mb-5 flex items-center justify-between"><div><p className="text-sm font-black text-slate-950">Thiết lập email report</p><p className="text-xs text-slate-500">Campaign {campaignId}</p></div><button type="button" onClick={() => setEmailOpen(false)} className="rounded-lg px-3 py-2 text-xs font-bold text-slate-500 hover:bg-slate-100">Đóng</button></div><EmailStep brief={{ brand: campaign.title, objective: displayOrder.objective || 'awareness' }} zones={[]} selectedZoneIds={[]} audiences={[]} data={{ campaignId }} formState={reportForm} isDone={false} onChange={() => {}} /></div></div>}
  </main>
}
