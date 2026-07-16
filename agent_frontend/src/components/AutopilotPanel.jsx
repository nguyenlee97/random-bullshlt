import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, AlertTriangle, Check, Circle, Loader2, Pause, Play, RotateCw,
  ShieldCheck, Sparkles, Square, Upload, X,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'
import StrategySimulator from '@/components/StrategySimulator'

const POLICY_OPTIONS = [
  { value: 'critical_only', label: 'Duyệt các bước quan trọng', note: 'Khuyến nghị' },
  { value: 'review_every_stage', label: 'Duyệt từng giai đoạn', note: 'Kiểm soát tối đa' },
  { value: 'auto_build_draft', label: 'Tự xây dựng bản nháp', note: 'Dừng trước launch' },
]

const TASK_LABELS = {
  normalize_brief: 'Chuẩn hóa brief', validate_brief: 'Kiểm tra brief',
  generate_strategy: 'Xây dựng chiến lược', retrieve_audience: 'Tìm audience',
  derive_targeting: 'Thiết lập targeting',
  plan_placement_intent: 'Đề xuất placement sơ bộ',
  plan_creative_formats: 'Lập kế hoạch format',
  prepare_creatives: 'Chuẩn bị creative',
  analyze_creatives: 'Phân tích creative',
  rank_placements: 'Xếp hạng placements', assign_creatives: 'Gán creative',
  forecast: 'Dự báo reach & chi phí', build_order_draft: 'Tạo order draft',
  run_order_guard: 'Kiểm tra an toàn', launch_approval: 'Duyệt launch',
  create_order: 'Tạo order', verify_order: 'Xác minh order',
  create_setup_report: 'Tạo báo cáo setup',
}

const ARTIFACT_LABELS = {
  brief: 'brief', strategy: 'chiến lược', audience: 'audience',
  targeting: 'targeting', placement_intent: 'placement sơ bộ',
  creative_format_plan: 'kế hoạch format', creative: 'creative',
  creative_verdict: 'creative verdict',
  placements: 'placements', assignments: 'phân bổ creative', forecast: 'dự báo',
  order_draft: 'order draft', order: 'order', report: 'báo cáo',
}

const RUN_LABELS = {
  queued: 'Đang chờ', running: 'Đang chạy', waiting_review: 'Cần duyệt',
  paused: 'Tạm dừng', completed: 'Hoàn tất', cancelled: 'Đã hủy', failed: 'Có lỗi',
}

const taskIcon = status => {
  if (status === 'succeeded') return <Check className="h-3 w-3" />
  if (status === 'running') return <Loader2 className="h-3 w-3 animate-spin" />
  if (status === 'waiting_review') return <AlertTriangle className="h-3 w-3" />
  if (['failed', 'cancelled'].includes(status)) return <X className="h-3 w-3" />
  return <Circle className="h-2.5 w-2.5" />
}

const evidenceText = evidence => {
  if (evidence.type === 'audience_pipeline') return `RAG ${evidence.retrieval_candidates || 0} candidates → rerank ${evidence.reranked ? 'đã áp dụng' : evidence.rerank_enabled ? 'không khả dụng' : 'tắt'} → ${evidence.selector || 'selector'}`
  if (evidence.type === 'catalog_segments') return `${evidence.count || 0} segment catalog: ${(evidence.ids || []).slice(0, 6).join(', ')}${(evidence.ids || []).length > 6 ? '…' : ''}`
  if (evidence.type === 'order_guard') return `Order guard: ${evidence.passed ? 'PASS' : 'BLOCKED'}`
  if (evidence.type === 'order_draft') return `Order draft: ${evidence.placements || 0} placements · idempotency ${evidence.idempotency_key || '—'}`
  if (evidence.type === 'order_create') return `Order create: ${evidence.order_id || 'đã ghi nhận'} · idempotency ${evidence.idempotency_key || '—'}`
  if (evidence.type === 'strategy_simulation') return `Simulator ${evidence.option_ids?.length || 0} phương án · đề xuất ${evidence.selected}`
  if (evidence.type === 'creative_source') return `Creative ${evidence.source === 'ai_generate' ? 'AI tự tạo' : 'do người dùng tải lên'} · ${evidence.count || 0} file${evidence.reused ? ' · tái sử dụng' : ''}`
  if (evidence.type === 'placement_intent') return `${evidence.candidate_count || 0} placement sơ bộ · ${evidence.conflict_count || 0} conflict · chưa lọc theo creative`
  if (evidence.type === 'creative_format_plan') return `${evidence.format_count || 0} format: ${(evidence.format_ids || []).join(', ')} · tối đa ${evidence.max_assets || 0} asset · ${evidence.estimated_provider_calls || 0} provider call`
  if (evidence.type === 'creative_generation') return `AI tạo ${evidence.count || 0} creative: ${(evidence.format_ids || []).join(', ')}${(evidence.failed_formats || []).length ? ` · lỗi ${(evidence.failed_formats || []).join(', ')}` : ''}`
  if (evidence.type === 'creative_verdicts') return `${evidence.count || 0} creative verdict · ${evidence.revalidated ? 'đã revalidate' : 'hiện hành'}`
  return evidence.type?.replaceAll('_', ' ') || 'evidence'
}

const localToday = () => {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

const validateBrief = brief => {
  const errors = []
  if (!String(brief?.brand || '').trim()) errors.push('thiếu thương hiệu')
  if (!['awareness', 'consideration', 'conversion', 'retention'].includes(brief?.objective)) {
    errors.push('mục tiêu chiến dịch không hợp lệ')
  }
  if (!(Number(brief?.budget) > 0)) errors.push('ngân sách phải lớn hơn 0')
  if (!brief?.startDate) errors.push('thiếu ngày bắt đầu')
  if (!brief?.endDate) errors.push('thiếu ngày kết thúc')
  if (brief?.startDate && brief?.endDate && brief.startDate > brief.endDate) {
    errors.push('ngày bắt đầu phải trước ngày kết thúc')
  }
  if (brief?.endDate && brief.endDate < localToday()) errors.push('ngày kết thúc đã ở quá khứ')
  return errors
}

export default function AutopilotPanel({ brief, canonicalWorkspace, onWorkspaceRefresh, onOpenChat, onOpenBrief, onOpenCreative, onStatusChange }) {
  const [policy, setPolicy] = useState('critical_only')
  const [creativeSource, setCreativeSource] = useState(null)
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState(canonicalWorkspace)
  const [pendingProposals, setPendingProposals] = useState([])
  const [prerequisitesLoading, setPrerequisitesLoading] = useState(true)
  const workspaceRefreshRef = useRef(onWorkspaceRefresh)

  useEffect(() => {
    workspaceRefreshRef.current = onWorkspaceRefresh
  }, [onWorkspaceRefresh])

  useEffect(() => {
    if (canonicalWorkspace) {
      setWorkspaceSnapshot(canonicalWorkspace)
      if (['upload', 'ai_generate'].includes(canonicalWorkspace.creative_source)) {
        setCreativeSource(canonicalWorkspace.creative_source)
      }
    }
  }, [canonicalWorkspace])

  const chooseCreativeSource = async value => {
    if (loading) return
    setLoading(true)
    setCreativeSource(value)
    setError('')
    try {
      const result = await AgentAPI.setWorkspacePreferences('autopilot', policy, value)
      if (result?.ok === false) throw new Error(result?.detail || 'Không thể lưu lựa chọn creative.')
      await loadPrerequisites()
    } catch (err) {
      setCreativeSource(null)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const loadPrerequisites = useCallback(async () => {
    const [workspace, proposals] = await Promise.all([
      workspaceRefreshRef.current?.() || AgentAPI.getWorkspace(),
      AgentAPI.getPendingWorkspaceProposals(),
    ])
    if (workspace) setWorkspaceSnapshot(workspace)
    setPendingProposals(proposals)
    setPrerequisitesLoading(false)
    return { workspace, proposals }
  }, [])

  useEffect(() => {
    loadPrerequisites()
    if (run?.run_id) return undefined
    const timer = setInterval(loadPrerequisites, 3000)
    return () => clearInterval(timer)
  }, [loadPrerequisites, run?.run_id])

  const refresh = useCallback(async () => {
    if (!run?.run_id) return
    const [current] = await Promise.all([
      AgentAPI.getAutopilotRun(run.run_id),
      loadPrerequisites(),
    ])
    if (current) {
      setRun(current)
    }
  }, [loadPrerequisites, run?.run_id])

  useEffect(() => {
    if (!run?.run_id || ['completed', 'cancelled', 'failed'].includes(run.status)) return
    const unsubscribe = AgentAPI.subscribeAutopilot(run.run_id, refresh)
    const timer = setInterval(refresh, 3000)
    return () => { unsubscribe?.(); clearInterval(timer) }
  }, [run?.run_id, run?.status, refresh])

  const start = async () => {
    setLoading(true)
    setError('')
    try {
      const { workspace, proposals } = await loadPrerequisites()
      if (proposals.length) {
        const fields = [...new Set(proposals.map(item => item.field || 'workspace'))]
        throw new Error(`Hãy duyệt hoặc hủy đề xuất đang chờ trong Chat trước: ${fields.join(', ')}.`)
      }
      const canonicalBrief = workspace?.artifacts?.brief?.value
      const validationErrors = validateBrief(canonicalBrief)
      if (!canonicalBrief || validationErrors.length) {
        throw new Error(`Brief đã duyệt chưa hợp lệ: ${validationErrors.join(', ')}.`)
      }
      if (!creativeSource) {
        throw new Error('Hãy chọn tải creative lên hoặc để AI tự tạo trước khi bắt đầu.')
      }
      const created = await AgentAPI.startAutopilot(policy, creativeSource)
      if (!created?.run_id) throw new Error(created?.detail || 'Không thể khởi động Campaign Autopilot.')
      setRun(created)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const act = async action => {
    setLoading(true)
    setError('')
    try {
      const next = await AgentAPI.autopilotAction(run.run_id, action)
      if (!next?.run_id) throw new Error(next?.detail || 'Không thể cập nhật Autopilot run.')
      setRun(next)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const review = async (task, approved) => {
    if (!run?.run_id || ['completed', 'cancelled', 'failed'].includes(run.status)) return
    setLoading(true)
    setError('')
    try {
      const next = await AgentAPI.reviewAutopilotTask(run.run_id, task.task_id, approved)
      if (!next?.run_id) throw new Error(next?.detail || 'Không thể ghi nhận review.')
      setRun(next)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const chooseStrategy = async optionId => {
    if (!run?.run_id || ['completed', 'cancelled', 'failed'].includes(run.status)) return
    setLoading(true)
    setError('')
    try {
      const next = await AgentAPI.selectAutopilotStrategy(run.run_id, optionId)
      if (!next?.run_id) throw new Error(next?.detail || 'Không thể cập nhật chiến lược.')
      setRun(next)
      await onWorkspaceRefresh?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const progress = useMemo(() => {
    if (!run?.tasks?.length) return 0
    const done = run.tasks.filter(task => ['succeeded', 'skipped'].includes(task.status)).length
    return Math.round(done / run.tasks.length * 100)
  }, [run])

  const runTerminal = ['completed', 'cancelled', 'failed'].includes(run?.status)
  const waiting = runTerminal ? null : run?.tasks?.find(task => task.status === 'waiting_review')
  const strategyTask = run?.tasks?.find(task => task.key === 'generate_strategy')
  const formatPlanTask = run?.tasks?.find(task => task.key === 'plan_creative_formats')
  const formatPlan = formatPlanTask?.result?.formats
    ? formatPlanTask.result
    : formatPlanTask?.pending_artifact?.value
  const orderCreated = run?.tasks?.some(task => task.key === 'create_order' && task.status === 'succeeded')
  const strategyCanChange = Boolean(strategyTask && ['waiting_review', 'succeeded'].includes(strategyTask.status) && !orderCreated && !runTerminal)
  const evidenceRows = useMemo(() => (run?.tasks || []).flatMap(task =>
    (task.evidence || []).map((evidence, index) => ({
      key: `${task.task_id}:${index}`, task: TASK_LABELS[task.key] || task.key,
      evidence,
    }))), [run])
  const canonicalBrief = workspaceSnapshot?.artifacts?.brief?.value || null
  const pendingBrief = pendingProposals.some(item => item.artifact === 'brief' || item.field === 'brief')
  const pendingFields = [...new Set(pendingProposals.map(item => item.field || 'workspace'))]
  const displayBrief = canonicalBrief || brief || {}
  const briefErrors = useMemo(() => validateBrief(canonicalBrief), [canonicalBrief])
  const briefReady = Boolean(canonicalBrief) && briefErrors.length === 0 && !pendingProposals.length && !prerequisitesLoading
  const retryAction = waiting?.result?.review_action === 'retry'
  const briefRetry = retryAction && waiting?.key === 'validate_brief'
  const retryReady = !briefRetry || (Boolean(canonicalBrief) && briefErrors.length === 0 && !pendingBrief)
  const waitingMessage = waiting?.result?.message
    || (waiting?.result?.errors || []).join(' · ')
    || (waiting?.key === 'launch_approval'
      ? 'Kiểm tra bản order cuối cùng trước khi tạo chiến dịch.'
      : 'Kiểm tra bằng chứng và xác nhận để tiếp tục.')

  useEffect(() => {
    onStatusChange?.(run ? {
      status: run.status,
      progress,
      waitingReview: Boolean(waiting),
    } : null)
  }, [onStatusChange, progress, run?.status, waiting?.task_id])

  return (
    <section className="h-full w-full overflow-y-auto bg-slate-50/70 p-3 sm:p-5" aria-label="Không gian Campaign Autopilot">
      {!run ? (
        <div className="mx-auto max-w-5xl space-y-4 pb-6">
          <div className="overflow-hidden rounded-3xl border border-brand-100 bg-[radial-gradient(circle_at_top_right,_#dcebff_0,_#ffffff_48%)] p-5 shadow-sm sm:p-7">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand-500 text-white shadow-[0_10px_24px_rgba(0,104,255,0.24)]">
                <Sparkles className="h-6 w-6" />
              </div>
              <div className="max-w-2xl">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-600">Agentic workspace</p>
                <h2 className="mt-1 text-xl font-black tracking-tight text-slate-900 sm:text-2xl">Campaign Autopilot</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Trao brief cho Agent, chọn mức kiểm soát rồi theo dõi kế hoạch, bằng chứng và các điểm cần duyệt trong một không gian riêng.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <div className="mb-3">
              <p className="text-sm font-black text-slate-900">Creative cho chiến dịch</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">Chọn cách chuẩn bị creative. Lựa chọn này độc lập với chính sách duyệt của Agent.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <button type="button" onClick={() => chooseCreativeSource('upload')}
                aria-pressed={creativeSource === 'upload'}
                className={`rounded-2xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-100 ${creativeSource === 'upload' ? 'border-brand-400 bg-brand-50 shadow-sm' : 'border-slate-200 hover:border-brand-200 hover:bg-brand-50/50'}`}>
                <span className="flex items-center gap-2 text-sm font-bold text-slate-900"><Upload className="h-4 w-4 text-brand-600" /> Tôi sẽ tải creative lên</span>
                <span className="mt-2 block text-xs leading-5 text-slate-500">Agent sẽ tạm dừng ở bước Creative để bạn tải file và duyệt kết quả phân tích.</span>
                {creativeSource === 'upload' && <span className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-brand-700"><Check className="h-3 w-3" /> Đã chọn</span>}
              </button>
              <button type="button" onClick={() => chooseCreativeSource('ai_generate')}
                aria-pressed={creativeSource === 'ai_generate'}
                className={`rounded-2xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-100 ${creativeSource === 'ai_generate' ? 'border-brand-400 bg-brand-50 shadow-sm' : 'border-slate-200 hover:border-brand-200 hover:bg-brand-50/50'}`}>
                <span className="flex items-center gap-2 text-sm font-bold text-slate-900"><Sparkles className="h-4 w-4 text-brand-600" /> Để AI tự tạo creative</span>
                <span className="mt-2 block text-xs leading-5 text-slate-500">Agent tự tạo, lưu và kiểm tra creative. Bạn chỉ cần review nếu có rủi ro hoặc độ tin cậy thấp.</span>
                {creativeSource === 'ai_generate' && <span className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-brand-700"><Check className="h-3 w-3" /> Đã chọn</span>}
              </button>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="mb-4">
                <p className="text-sm font-black text-slate-900">Chọn cách Agent xin duyệt</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">Có thể tạm dừng hoặc chuyển về quy trình hướng dẫn bất cứ lúc nào.</p>
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                {POLICY_OPTIONS.map(item => (
                  <button key={item.value} type="button" onClick={() => setPolicy(item.value)}
                    aria-pressed={policy === item.value}
                    className={`min-h-24 rounded-2xl border p-3 text-left transition-all focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-100 ${policy === item.value ? 'border-brand-400 bg-brand-50 text-brand-800 shadow-sm' : 'border-slate-200 bg-white text-slate-600 hover:border-brand-200 hover:bg-brand-50/50'}`}>
                    <span className="block text-xs font-bold leading-5">{item.label}</span>
                    <span className="mt-1 block text-[10px] opacity-70">{item.note}</span>
                    {policy === item.value && <span className="mt-3 inline-flex items-center gap-1 text-[10px] font-bold text-brand-700"><Check className="h-3 w-3" /> Đang chọn</span>}
                  </button>
                ))}
              </div>
            </div>

            <aside className={`rounded-2xl border p-4 shadow-sm ${briefReady ? 'border-green-200 bg-green-50/70' : 'border-amber-200 bg-amber-50/70'}`}>
              <div className="flex items-center gap-2">
                {briefReady ? <Check className="h-4 w-4 text-green-700" /> : <AlertTriangle className="h-4 w-4 text-amber-700" />}
                <p className={`text-xs font-black uppercase tracking-wide ${briefReady ? 'text-green-800' : 'text-amber-900'}`}>
                  {pendingBrief ? 'Brief đang chờ duyệt' : briefReady ? 'Brief sẵn sàng' : 'Brief chưa hợp lệ'}
                </p>
              </div>
              <dl className="mt-3 space-y-2 text-xs">
                <div><dt className="text-slate-500">Thương hiệu</dt><dd className="font-bold text-slate-800">{displayBrief?.brand || 'Chưa có'}</dd></div>
                <div><dt className="text-slate-500">Ngân sách</dt><dd className="font-bold text-slate-800">{Number(displayBrief?.budget) > 0 ? `${displayBrief.budget} triệu đồng` : 'Chưa có'}</dd></div>
                <div><dt className="text-slate-500">Thời gian</dt><dd className="font-bold text-slate-800">{displayBrief?.startDate && displayBrief?.endDate ? `${displayBrief.startDate} → ${displayBrief.endDate}` : 'Chưa có'}</dd></div>
              </dl>
              {pendingProposals.length > 0 && <p className="mt-3 text-[11px] leading-5 text-amber-800">Đang chờ duyệt hoặc hủy đề xuất: {pendingFields.join(', ')}. Autopilot sẽ không tự ghi các thay đổi này.</p>}
              {!pendingProposals.length && !briefReady && <p className="mt-3 text-[11px] leading-5 text-amber-800">Cần xử lý: {briefErrors.join(', ')}.</p>}
              <button type="button" onClick={onOpenBrief} className="mt-4 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:border-brand-300 hover:text-brand-700">
                {briefReady ? 'Xem hoặc chỉnh brief' : 'Mở form Brief'}
              </button>
            </aside>
          </div>

          <div className="flex flex-col items-stretch justify-between gap-3 rounded-2xl border border-brand-100 bg-white p-4 shadow-sm sm:flex-row sm:items-center">
            <div>
              <p className="text-sm font-bold text-slate-900">Sẵn sàng để Agent lập kế hoạch?</p>
              <p className="mt-1 text-xs text-slate-500">Agent luôn dừng trước hành động tạo order để bạn xác nhận.</p>
            </div>
            <button type="button" disabled={!briefReady || !creativeSource || loading || prerequisitesLoading} onClick={start}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-brand-500 px-6 text-sm font-bold text-white shadow-sm hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
              Bắt đầu Autopilot
            </button>
          </div>
        </div>
      ) : (
        <div className="mx-auto max-w-6xl space-y-4 pb-24">
          <div className="sticky top-0 z-10 -mx-1 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur-md sm:p-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-500" />
              <span className="text-sm font-bold text-slate-900">Campaign Autopilot</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">Plan v{run.plan_revision || 1}</span>
              <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-bold text-brand-700">{run.creative_source === 'ai_generate' ? 'AI tự tạo creative' : 'Creative tải lên'}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${run.status === 'waiting_review' ? 'bg-amber-100 text-amber-800' : run.status === 'failed' ? 'bg-red-100 text-red-700' : run.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-brand-50 text-brand-700'}`}>{RUN_LABELS[run.status] || run.status}</span>
            </div>
            <div className="h-1.5 min-w-[130px] flex-1 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
            <span className="text-xs font-semibold text-slate-600">{progress}%</span>
            <div className="flex gap-1.5">
              {run.status === 'paused' && !run.replan_blocked ? (
                <button onClick={() => act('resume')} disabled={loading} className="rounded-lg border border-brand-200 p-2 text-brand-600 hover:bg-brand-50" title="Tiếp tục" aria-label="Tiếp tục Autopilot"><Play className="h-3.5 w-3.5" /></button>
              ) : !['completed', 'cancelled', 'failed'].includes(run.status) && (
                <button onClick={() => act('pause')} disabled={loading} className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50" title="Tạm dừng" aria-label="Tạm dừng Autopilot"><Pause className="h-3.5 w-3.5" /></button>
              )}
              {!['completed', 'cancelled'].includes(run.status) && <button onClick={() => act('cancel')} disabled={loading} className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:border-red-200 hover:bg-red-50 hover:text-red-600" title="Hủy run" aria-label="Hủy Autopilot run"><Square className="h-3.5 w-3.5" /></button>}
              <button onClick={refresh} disabled={loading} className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50" title="Làm mới" aria-label="Làm mới trạng thái Autopilot"><RotateCw className="h-3.5 w-3.5" /></button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm sm:p-4">
            <p className="mb-3 text-xs font-black uppercase tracking-wide text-slate-500">Tiến độ thực thi</p>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {run.tasks.map(task => (
                <div key={task.task_id} title={task.error || task.result?.message || TASK_LABELS[task.key]}
                  className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-medium ${task.status === 'succeeded' ? 'border-green-200 bg-green-50 text-green-700' : task.status === 'running' ? 'border-brand-300 bg-brand-50 text-brand-700' : task.status === 'waiting_review' ? 'border-amber-300 bg-amber-50 text-amber-800' : task.status === 'failed' ? 'border-red-200 bg-red-50 text-red-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
                  {taskIcon(task.status)} {TASK_LABELS[task.key] || task.key}
                </div>
              ))}
            </div>
          </div>

          {run.replan_blocked && (
            <div className="rounded-xl border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
              <p className="font-bold">Run đã dừng an toàn sau khi order được tạo.</p>
              <p className="mt-0.5">Workspace có thay đổi mới. Hãy chọn “Chiến dịch mới” để tạo một run khác; Advertising Agent sẽ không tự tạo lại order.</p>
            </div>
          )}

          {run.last_replan && !run.replan_blocked && (
            <div className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-xs text-brand-800">
              <span className="font-bold">Kế hoạch đã được tính lại.</span>{' '}
              Thay đổi ở {run.last_replan.changed_artifacts.map(item => ARTIFACT_LABELS[item] || item).join(', ')} ảnh hưởng {run.last_replan.affected_tasks.length} tác vụ; các kết quả không liên quan được giữ nguyên.
            </div>
          )}

          <StrategySimulator
            value={strategyTask?.result}
            busy={loading}
            canSelect={strategyCanChange}
            onSelect={chooseStrategy}
          />

          {formatPlan?.formats?.length > 0 && (
            <section className="rounded-2xl border border-brand-100 bg-white p-4 shadow-sm" aria-label="Kế hoạch định dạng creative">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-brand-700">Kế hoạch creative theo placement</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    Agent gộp các placement cùng kích thước và chỉ chuẩn bị tối đa {formatPlan.max_assets} asset cần thiết.
                  </p>
                </div>
                <span className="rounded-full bg-brand-50 px-2.5 py-1 text-[10px] font-bold text-brand-700">
                  {formatPlan.source === 'ai_generate' ? `${formatPlan.estimated_provider_calls || 0} lượt tạo AI` : 'Dùng file tải lên'}
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {formatPlan.formats.map(item => (
                  <div key={item.format_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <p className="text-xs font-bold text-slate-800">{item.width} × {item.height}</p>
                    <p className="mt-0.5 truncate text-[10px] text-slate-500" title={item.format_id}>{item.format_id}</p>
                    <p className="mt-1 text-[10px] font-semibold text-brand-700">Phủ {item.zone_ids?.length || 0} placement</p>
                  </div>
                ))}
              </div>
              {(formatPlan.unsupported_zone_ids?.length > 0 || formatPlan.omitted_by_cost_cap_zone_ids?.length > 0) && (
                <p className="mt-3 text-[11px] leading-5 text-amber-700">
                  {formatPlan.unsupported_zone_ids?.length || 0} placement chưa có format hỗ trợ; {formatPlan.omitted_by_cost_cap_zone_ids?.length || 0} placement ngoài giới hạn chi phí.
                </p>
              )}
            </section>
          )}

          <details className="rounded-xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-bold text-slate-700">
              <Activity className="h-4 w-4 text-brand-500" /> Bằng chứng vận hành
              <span className="font-normal text-slate-500">trace · RAG/rerank · guard · idempotency</span>
            </summary>
            <div className="mt-2 space-y-1.5 text-[11px]">
              <p className="rounded-lg bg-white px-2 py-1.5 text-slate-600"><span className="font-bold text-slate-800">Run trace:</span> {run.trace_id || run.run_id}</p>
              {evidenceRows.length ? evidenceRows.map(row => (
                <p key={row.key} className="rounded-lg bg-white px-2 py-1.5 text-slate-600">
                  <span className="font-bold text-slate-800">{row.task}:</span> {evidenceText(row.evidence)}
                </p>
              )) : <p className="px-2 py-1 text-slate-500">Bằng chứng sẽ xuất hiện khi các tác vụ hoàn tất.</p>}
            </div>
          </details>

          {waiting && (
            <div className="sticky bottom-2 z-10 flex flex-col gap-3 rounded-2xl border border-amber-300 bg-amber-50/95 p-3 shadow-[0_12px_36px_rgba(120,80,0,0.18)] backdrop-blur-md sm:flex-row sm:items-center">
              <ShieldCheck className="h-5 w-5 shrink-0 text-amber-700" />
              <div className="flex-1">
                <p className="text-xs font-bold text-amber-900">Cần bạn review: {TASK_LABELS[waiting.key]}</p>
                <p className="mt-0.5 text-xs text-amber-800">{waitingMessage}</p>
                {briefRetry && !retryReady && (
                  <p className="mt-1 text-[11px] font-semibold text-amber-900">
                    {pendingBrief ? 'Duyệt hoặc hủy đề xuất Brief trong Chat trước.' : `Sửa Brief trước khi kiểm tra lại: ${briefErrors.join(', ')}.`}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {briefRetry && pendingBrief && <button onClick={onOpenChat} className="rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900">Mở Chat để duyệt</button>}
                {briefRetry && !pendingBrief && !retryReady && <button onClick={onOpenBrief} className="rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900">Sửa Brief</button>}
                {waiting.result?.reason === 'missing_creative' && <button onClick={onOpenCreative} className="rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900">Mở Creative</button>}
                <button onClick={() => review(waiting, false)} disabled={loading} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700">Từ chối</button>
                <button onClick={() => review(waiting, true)} disabled={loading || (retryAction && !retryReady)} className={`rounded-lg px-3 py-1.5 text-xs font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300 ${waiting.key === 'launch_approval' ? 'bg-red-600 hover:bg-red-700' : 'bg-brand-500 hover:bg-brand-600'}`}>
                  {retryAction ? 'Kiểm tra lại' : waiting.key === 'launch_approval' ? 'Duyệt & tạo order' : 'Duyệt & tiếp tục'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {error && <p className="mx-auto mt-3 max-w-6xl rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700" role="alert">{error}</p>}
    </section>
  )
}
