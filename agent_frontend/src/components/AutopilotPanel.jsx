import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, Check, Circle, Loader2, Pause, Play, RotateCw,
  ExternalLink, ImageIcon, ListChecks, ShieldCheck, Sparkles, Square, Upload, X,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'
import AutopilotReview from '@/components/AutopilotReview'
import StrategySimulator from '@/components/StrategySimulator'
import AutopilotOutcome from '@/components/AutopilotOutcome'
import { creativePlacementCoverage } from '@/lib/campaignOutcome'
import { defaultPlacementSelection, mergeCreativeVerdicts } from '@/lib/creativeIntel'

const ADSPILOT_URL = import.meta.env.VITE_ADSPILOT_URL || 'https://adspilot.pawgrammers.io.vn'

const POLICY_OPTIONS = [
  { value: 'critical_only', label: 'Duyệt các bước quan trọng', note: '5 checkpoint · Khuyến nghị' },
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

const TASK_ORDER = [
  'normalize_brief', 'validate_brief', 'generate_strategy', 'retrieve_audience',
  'derive_targeting', 'plan_placement_intent', 'plan_creative_formats',
  'prepare_creatives', 'analyze_creatives', 'rank_placements', 'assign_creatives',
  'forecast', 'build_order_draft', 'run_order_guard', 'launch_approval',
  'create_order', 'verify_order', 'create_setup_report',
]

const TASK_ORDER_INDEX = Object.fromEntries(TASK_ORDER.map((key, index) => [key, index]))

const AUTOPILOT_STAGES = [
  { label: 'Brief & chiến lược', keys: ['normalize_brief', 'validate_brief', 'generate_strategy'] },
  { label: 'Audience & targeting', keys: ['retrieve_audience', 'derive_targeting'] },
  { label: 'Placement & creative', keys: ['plan_placement_intent', 'plan_creative_formats', 'prepare_creatives', 'analyze_creatives', 'rank_placements', 'assign_creatives'] },
  { label: 'Dự báo & an toàn', keys: ['forecast', 'build_order_draft', 'run_order_guard'] },
  { label: 'Launch & hoàn tất', keys: ['launch_approval', 'create_order', 'verify_order', 'create_setup_report'] },
]

const taskStatusClass = status => {
  if (status === 'succeeded') return 'border-green-200 bg-green-50 text-green-700'
  if (status === 'running') return 'border-brand-300 bg-brand-50 text-brand-700'
  if (status === 'waiting_review') return 'border-amber-300 bg-amber-50 text-amber-800'
  if (['failed', 'cancelled'].includes(status)) return 'border-red-200 bg-red-50 text-red-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

const stageStatus = tasks => {
  const statuses = tasks.map(task => task?.status).filter(Boolean)
  if (statuses.some(status => ['failed', 'cancelled'].includes(status))) return 'failed'
  if (statuses.includes('waiting_review')) return 'waiting_review'
  if (statuses.includes('running')) return 'running'
  if (statuses.length && statuses.every(status => ['succeeded', 'skipped'].includes(status))) return 'succeeded'
  if (statuses.some(status => ['succeeded', 'skipped'].includes(status))) return 'running'
  return 'pending'
}

const formatNumber = value => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 }).format(Number(value || 0))
const audienceName = item => item.fullLabel || item.label || item.name || item.code || item._id || 'Segment'

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
  if (evidence.type === 'forecast_inputs') return `${evidence.method || 'forecast'} · ${evidence.zone_count || 0} placement · CPM ${formatNumber(evidence.average_cpm)} ₫ · tần suất ${evidence.frequency || '—'}`
  if (evidence.type === 'creative_source') return `Creative ${evidence.source === 'ai_generate' ? 'AI tự tạo' : 'do người dùng tải lên'} · ${evidence.count || 0} file${evidence.reused ? ' · tái sử dụng' : ''}`
  if (evidence.type === 'creative_format_coverage') return `Creative phủ ${evidence.covered || 0}/${evidence.required || 0} format · còn thiếu ${(evidence.missing || []).map(item => `${item.width}×${item.height}`).join(', ') || 'không'}`
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

export default function AutopilotPanel({
  brief, canonicalWorkspace, initialRun = null, onWorkspaceRefresh,
  onOpenChat, onOpenBrief, onOpenAudience, onOpenCreative, onOpenAssignments, onStatusChange,
  reportState, onReportChange, onSendReportQuestion,
  onReportActivate, onReportExit,
}) {
  const [policy, setPolicy] = useState('critical_only')
  const [creativeSource, setCreativeSource] = useState(null)
  const [creativeDirection, setCreativeDirection] = useState('')
  const [creativeAssets, setCreativeAssets] = useState([])
  const [creativeAssetIds, setCreativeAssetIds] = useState(new Set())
  const [assetName, setAssetName] = useState('')
  const [assetUploading, setAssetUploading] = useState(false)
  const [run, setRun] = useState(initialRun)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState(canonicalWorkspace)
  const [pendingProposals, setPendingProposals] = useState([])
  const [prerequisitesLoading, setPrerequisitesLoading] = useState(true)
  const [placementSelection, setPlacementSelection] = useState([])
  const workspaceRefreshRef = useRef(onWorkspaceRefresh)

  useEffect(() => {
    workspaceRefreshRef.current = onWorkspaceRefresh
  }, [onWorkspaceRefresh])

  useEffect(() => {
    setRun(initialRun || null)
  }, [initialRun?.run_id])

  useEffect(() => {
    AgentAPI.listCreativeAssets().then(setCreativeAssets)
  }, [])

  const uploadAutopilotAsset = useCallback(async event => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !assetName.trim()) {
      setError('Hãy đặt tên asset trước khi chọn ảnh.')
      return
    }
    setAssetUploading(true)
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file)
      })
      const asset = await AgentAPI.createCreativeAsset({
        name: assetName, kind: 'style_reference', useInstruction: creativeDirection,
        required: true, dataUrl,
      })
      setCreativeAssets(previous => [asset, ...previous])
      setCreativeAssetIds(previous => new Set([...previous, asset.asset_id]))
      setAssetName('')
    } catch (uploadError) {
      setError(uploadError.message)
    } finally {
      setAssetUploading(false)
    }
  }, [assetName, creativeDirection])

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
      if (creativeSource === 'ai_generate' && !creativeDirection.trim()) {
        throw new Error('Hãy mô tả creative direction trước khi để Autopilot tạo ảnh.')
      }
      const startKey = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
      const created = await AgentAPI.startAutopilot(policy, creativeSource, startKey, {
        direction: creativeDirection, assetIds: [...creativeAssetIds],
      })
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
      let reviewedTask = task
      if (approved && task.key === 'plan_placement_intent') {
        if (!placementSelection.length) throw new Error('Hãy giữ lại ít nhất một placement.')
        const selected = await AgentAPI.selectAutopilotPlacements(
          run.run_id,
          placementSelection,
          'Operator adjusted placement shortlist in review',
        )
        if (!selected?.run_id) throw new Error(selected?.detail || 'Không thể lưu shortlist placement.')
        reviewedTask = selected.tasks?.find(item => item.task_id === task.task_id) || task
      }
      const next = await AgentAPI.reviewAutopilotTask(run.run_id, reviewedTask.task_id, approved)
      if (!next?.run_id) throw new Error(next?.detail || 'Không thể ghi nhận review.')
      setRun(next)
      return next
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setLoading(false)
    }
  }

  const openEditor = editor => {
    setError('')
    editor?.()
  }

  const cancelRunWithConfirmation = async () => {
    if (!globalThis.confirm?.('Hủy run hiện tại? Các artifact đã duyệt vẫn được giữ lại, nhưng Autopilot sẽ không tiếp tục run này.')) return
    await act('cancel')
  }

  const chooseStrategy = async optionId => {
    if (!run?.run_id || !strategyCanChange) return
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

  const orderedTasks = useMemo(() => [...(run?.tasks || [])].sort((left, right) => (
    (TASK_ORDER_INDEX[left.key] ?? TASK_ORDER.length) - (TASK_ORDER_INDEX[right.key] ?? TASK_ORDER.length)
  )), [run?.tasks])
  const taskByKey = useMemo(() => Object.fromEntries(
    orderedTasks.map(task => [task.key, task])
  ), [orderedTasks])
  const progress = useMemo(() => {
    if (!orderedTasks.length) return 0
    const done = orderedTasks.filter(task => ['succeeded', 'skipped'].includes(task.status)).length
    return Math.round(done / orderedTasks.length * 100)
  }, [orderedTasks])

  const runTerminal = ['completed', 'cancelled', 'failed'].includes(run?.status)
  const waiting = runTerminal ? null : orderedTasks.find(task => task.status === 'waiting_review')
  const placementCandidateKey = waiting?.key === 'plan_placement_intent'
    ? (waiting.pending_artifact?.value?.candidate_zone_ids || waiting.result?.candidate_zone_ids || []).join('|')
    : ''
  const strategyTask = taskByKey.generate_strategy
  const formatPlanTask = taskByKey.plan_creative_formats
  const formatPlan = formatPlanTask?.result?.formats
    ? formatPlanTask.result
    : formatPlanTask?.pending_artifact?.value
  const creativeTask = taskByKey.prepare_creatives
  const creativeValue = creativeTask?.result
    || creativeTask?.pending_artifact?.value
    || workspaceSnapshot?.artifacts?.creative?.value
    || {}
  const creativeFiles = mergeCreativeVerdicts(
    creativeValue,
    workspaceSnapshot?.artifacts?.creative_verdict?.value,
  ).files || []
  const assignmentResult = taskByKey.assign_creatives?.result
    || taskByKey.assign_creatives?.pending_artifact?.value
    || workspaceSnapshot?.artifacts?.assignments?.value
    || {}
  const creativeCoverage = creativePlacementCoverage(creativeFiles, assignmentResult)
  const placementResult = taskByKey.rank_placements?.result || taskByKey.rank_placements?.pending_artifact?.value || {}
  const audienceResult = taskByKey.retrieve_audience?.result || taskByKey.retrieve_audience?.pending_artifact?.value || {}
  const audienceCatalogCount = audienceResult.retrieval?.catalog_segments || audienceResult.retrieval?.total_segments || 0
  const forecastResult = taskByKey.forecast?.result || taskByKey.forecast?.pending_artifact?.value || {}
  const orderResult = taskByKey.verify_order?.result?.order || taskByKey.create_order?.result?.order || null
  const orderCreated = taskByKey.create_order?.status === 'succeeded'
  const strategyCanChange = waiting?.key === 'generate_strategy'
    && strategyTask?.status === 'waiting_review'
    && !orderCreated
    && !runTerminal
  const strategySelectionHint = orderCreated || runTerminal
    ? 'Phương án này là một phần của campaign đã hoàn tất.'
    : strategyCanChange
      ? 'Bạn có thể chọn phương án khác tại điểm review này. Autopilot sẽ giữ run hiện tại và chỉ tính lại các bước phụ thuộc.'
      : 'Phương án chỉ có thể thay đổi khi Autopilot đang dừng tại một điểm review.'
  const executionStages = AUTOPILOT_STAGES.map(stage => {
    const tasks = stage.keys.map(key => taskByKey[key]).filter(Boolean)
    const done = tasks.filter(task => ['succeeded', 'skipped'].includes(task.status)).length
    return { ...stage, tasks, done, status: stageStatus(tasks) }
  })
  const placementLinks = [...new Map(
    (placementResult.zones || []).filter(zone => zone.siteUrl).map(zone => [zone.siteUrl, zone])
  ).values()]
  const evidenceRows = useMemo(() => orderedTasks.flatMap(task =>
    (task.evidence || []).map((evidence, index) => ({
      key: `${task.task_id}:${index}`, task: TASK_LABELS[task.key] || task.key,
      evidence,
    }))), [orderedTasks])
  const canonicalBrief = workspaceSnapshot?.artifacts?.brief?.value || null
  const pendingBrief = pendingProposals.some(item => item.artifact === 'brief' || item.field === 'brief')
  const pendingFields = [...new Set(pendingProposals.map(item => item.field || 'workspace'))]
  const displayBrief = canonicalBrief || brief || {}
  const briefErrors = useMemo(() => validateBrief(canonicalBrief), [canonicalBrief])
  const briefReady = Boolean(canonicalBrief) && briefErrors.length === 0 && !pendingProposals.length && !prerequisitesLoading
  const briefHasDecisionContext = Boolean(String(displayBrief?.kpi || '').trim() && String(displayBrief?.notes || '').trim())
  const startBlockers = [
    !briefReady ? 'brief đã duyệt và hợp lệ' : null,
    !creativeSource ? 'nguồn creative (tải lên hoặc AI tự tạo)' : null,
    creativeSource === 'ai_generate' && !creativeDirection.trim() ? 'creative direction cho AI' : null,
  ].filter(Boolean)
  const retryAction = waiting?.result?.review_action === 'retry'
  const briefRetry = retryAction && waiting?.key === 'validate_brief'
  const retryReady = !briefRetry || (Boolean(canonicalBrief) && briefErrors.length === 0 && !pendingBrief)
  const waitingMessage = waiting?.result?.message
    || (waiting?.result?.errors || []).join(' · ')
    || (waiting?.key === 'launch_approval'
      ? 'Kiểm tra bản order cuối cùng trước khi tạo chiến dịch.'
      : 'Kiểm tra bằng chứng và xác nhận để tiếp tục.')
  const waitingEdits = waiting?.key === 'validate_brief'
    ? [{ label: 'Sửa Brief', action: onOpenBrief }]
    : ['retrieve_audience', 'derive_targeting'].includes(waiting?.key)
      ? [{
          label: waiting.key === 'derive_targeting' ? 'Chỉnh targeting' : 'Chỉnh audience',
          action: () => onOpenAudience?.({
            ...audienceResult,
            targeting: waiting.key === 'derive_targeting'
              ? (waiting.pending_artifact?.value || waiting.result || {})
              : (workspaceSnapshot?.artifacts?.targeting?.value || {}),
          }, waiting.key),
        }]
      : waiting?.key === 'assign_creatives'
        ? [
            {
              label: 'Chỉnh phân bổ creative',
              action: () => onOpenAssignments?.({
                placements: placementResult,
                creativeFiles,
                assignmentValue: waiting.result || assignmentResult,
              }),
            },
            { label: 'Tải creative mới', action: onOpenCreative },
          ]
        : ['prepare_creatives', 'analyze_creatives', 'rank_placements'].includes(waiting?.key)
          ? [{ label: waiting?.result?.reason === 'missing_creative' ? 'Tải creative lên' : 'Chỉnh hoặc thay creative', action: onOpenCreative }]
          : []

  useEffect(() => {
    if (waiting?.key !== 'plan_placement_intent') {
      setPlacementSelection([])
      return
    }
    setPlacementSelection(defaultPlacementSelection(
      waiting.pending_artifact?.value || waiting.result || {},
      6,
    ))
  }, [waiting?.task_id, placementCandidateKey])

  useEffect(() => {
    onStatusChange?.(run ? {
      status: run.status,
      progress,
      waitingReview: Boolean(waiting),
      waitingTaskId: waiting?.task_id || null,
      waitingTaskKey: waiting?.key || null,
      waitingMessage: waitingMessage || '',
    } : null)
  }, [onStatusChange, progress, run?.status, waiting?.task_id, waiting?.key, waitingMessage])

  return (
    <section data-demo="autopilot-canvas" className="h-full w-full overflow-y-auto bg-slate-50/70 p-3 sm:p-5" aria-label="Không gian Campaign Autopilot">
      {!run ? (
        <div className="mx-auto max-w-5xl space-y-4 pb-6">
          <div data-demo="autopilot-intro" className="overflow-hidden rounded-3xl border border-brand-100 bg-[radial-gradient(circle_at_top_right,_#dcebff_0,_#ffffff_48%)] p-5 shadow-sm sm:p-7">
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

          <section data-demo="autopilot-guide" className="overflow-hidden rounded-3xl border border-slate-800 bg-[radial-gradient(circle_at_top_right,_rgba(0,104,255,0.32),_transparent_38%),linear-gradient(145deg,_#07172f,_#020817)] p-4 text-white shadow-[0_20px_55px_rgba(15,48,92,0.16)] sm:p-5" aria-labelledby="autopilot-guide-title">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-300">Start here · 4 điều cần nhìn</p>
                <h3 id="autopilot-guide-title" className="mt-1 text-lg font-black tracking-tight">Chuẩn bị đúng đầu vào, rồi đọc Autopilot như một plan.</h3>
              </div>
              <p className="max-w-md text-xs leading-5 text-slate-400">Đây là guide nằm ngay trong workspace—không phải walkthrough. Bạn có thể quay lại bốn mốc này bất cứ lúc nào.</p>
            </div>
            <div className="mt-5 grid gap-2 md:grid-cols-4">
              <article className={`rounded-2xl border p-3.5 ${briefReady ? 'border-emerald-400/30 bg-emerald-400/10' : 'border-amber-300/30 bg-amber-300/10'}`}>
                <div className="flex items-center justify-between"><span className="text-[10px] font-black tracking-[0.16em] text-slate-400">01 · BRIEF</span>{briefReady ? <Check className="h-4 w-4 text-emerald-300" /> : <AlertTriangle className="h-4 w-4 text-amber-300" />}</div>
                <p className="mt-3 text-sm font-black">Đủ dữ kiện để lập plan</p>
                <p className="mt-1.5 text-[11px] leading-5 text-slate-400">Bắt buộc: brand, objective, budget và ngày chạy. KPI + ghi chú audience/thị trường giúp plan sắc hơn.</p>
                <button type="button" onClick={onOpenBrief} className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-cyan-300 hover:text-white">{briefReady && briefHasDecisionContext ? 'Brief đã đủ lực' : 'Mở và hoàn thiện Brief'} <ArrowRight className="h-3 w-3" /></button>
              </article>
              <article className={`rounded-2xl border p-3.5 ${creativeSource ? 'border-emerald-400/30 bg-emerald-400/10' : 'border-white/10 bg-white/[0.045]'}`}>
                <div className="flex items-center justify-between"><span className="text-[10px] font-black tracking-[0.16em] text-slate-400">02 · CREATIVE</span>{creativeSource ? <Check className="h-4 w-4 text-emerald-300" /> : <Circle className="h-3.5 w-3.5 text-slate-500" />}</div>
                <p className="mt-3 text-sm font-black">Chọn đúng loại đầu vào</p>
                <p className="mt-1.5 text-[11px] leading-5 text-slate-400">Upload khi đã có asset chính thức. Chọn AI generate khi cần Agent tạo draft theo format placement.</p>
                <p className="mt-3 text-[11px] font-bold text-cyan-300">{creativeSource === 'upload' ? 'Đã chọn: creative tải lên' : creativeSource === 'ai_generate' ? 'Đã chọn: AI tự tạo' : 'Chưa chọn nguồn creative'}</p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-white/[0.045] p-3.5">
                <div className="flex items-center justify-between"><span className="text-[10px] font-black tracking-[0.16em] text-slate-400">03 · CONTROL</span><ShieldCheck className="h-4 w-4 text-cyan-300" /></div>
                <p className="mt-3 text-sm font-black">Biết lúc Agent sẽ dừng</p>
                <p className="mt-1.5 text-[11px] leading-5 text-slate-400">Review policy quyết định số checkpoint. Dù chọn policy nào, launch vẫn là một điểm kiểm soát rõ ràng.</p>
                <p className="mt-3 text-[11px] font-bold text-cyan-300">{POLICY_OPTIONS.find(item => item.value === policy)?.label}</p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-white/[0.045] p-3.5">
                <div className="flex items-center justify-between"><span className="text-[10px] font-black tracking-[0.16em] text-slate-400">04 · RUN</span><ListChecks className="h-4 w-4 text-cyan-300" /></div>
                <p className="mt-3 text-sm font-black">Theo dõi plan, không chờ mù</p>
                <p className="mt-1.5 text-[11px] leading-5 text-slate-400">Sau khi chạy, nhìn stage, evidence và các checkpoint màu vàng. Mỗi artifact đều có đường quay lại để sửa.</p>
                <p className="mt-3 text-[11px] font-bold text-cyan-300">{startBlockers.length ? `${startBlockers.length} điều kiện còn thiếu` : 'Sẵn sàng bắt đầu run'}</p>
              </article>
            </div>
          </section>

          <div data-demo="autopilot-creative-source" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
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

          {creativeSource === 'ai_generate' && <div className="rounded-2xl border border-sky-200 bg-sky-50/50 p-4 space-y-3" data-testid="autopilot-creative-intake">
            <div><p className="text-sm font-black text-slate-900">Creative direction & assets cho Autopilot</p>
              <p className="mt-1 text-xs text-slate-500">Thông tin này được khóa vào run; Agent tự soạn prompt riêng cho từng format.</p></div>
            <textarea value={creativeDirection} onChange={event => setCreativeDirection(event.target.value)} rows={3}
              placeholder="Ví dụ: trẻ trung, màu đỏ thương hiệu, logo ở góc trái, tô bún bò là hero visual, không tự thêm giá…"
              className="w-full rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs" />
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <input value={assetName} onChange={event => setAssetName(event.target.value)} placeholder="Tên asset: Logo Hutao / Tô bún bò…"
                className="rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs" />
              <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-sky-700 px-4 py-2 text-xs font-bold text-white">
                {assetUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                Thêm ảnh<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" disabled={assetUploading} onChange={uploadAutopilotAsset} />
              </label>
            </div>
            {creativeAssets.length > 0 && <div className="flex flex-wrap gap-2">{creativeAssets.map(asset => {
              const selected = creativeAssetIds.has(asset.asset_id)
              return <button type="button" key={asset.asset_id} onClick={() => setCreativeAssetIds(previous => {
                const next = new Set(previous); next.has(asset.asset_id) ? next.delete(asset.asset_id) : next.add(asset.asset_id); return next
              })} className={`rounded-full border px-3 py-1.5 text-[11px] font-bold ${selected ? 'border-sky-500 bg-sky-100 text-sky-800' : 'border-slate-200 bg-white text-slate-600'}`}>
                {selected ? '✓ ' : ''}{asset.name} · {asset.kind}
              </button>
            })}</div>}
          </div>}

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div data-demo="autopilot-policy" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="mb-4">
                <p className="text-sm font-black text-slate-900">Chọn cách Agent xin duyệt</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">Có thể tạm dừng Autopilot bất cứ lúc nào; campaign này vẫn giữ nguyên mode đã chọn từ trang chủ.</p>
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
              {policy === 'critical_only' && (
                <p className="mt-3 rounded-xl border border-brand-100 bg-brand-50/70 px-3 py-2 text-[11px] leading-5 text-brand-800">
                  Agent sẽ dừng tại: Tìm audience → Thiết lập targeting → Đề xuất placement sơ bộ → Gán creative → Duyệt launch. Creative có rủi ro sẽ luôn dừng để review.
                </p>
              )}
            </div>

            <aside data-demo="autopilot-brief-status" className={`rounded-2xl border p-4 shadow-sm ${briefReady ? 'border-green-200 bg-green-50/70' : 'border-amber-200 bg-amber-50/70'}`}>
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

          <div data-demo="autopilot-start" className="flex flex-col items-stretch justify-between gap-3 rounded-2xl border border-brand-100 bg-white p-4 shadow-sm sm:flex-row sm:items-center">
            <div>
              <p className="text-sm font-bold text-slate-900">Sẵn sàng để Agent lập kế hoạch?</p>
              {startBlockers.length ? (
                <p className="mt-1 text-xs font-medium text-amber-700">
                  Còn thiếu: {startBlockers.join(' và ')}. Bấm bắt đầu để xem hướng dẫn chi tiết.
                </p>
              ) : (
                <p className="mt-1 text-xs text-slate-500">Agent luôn dừng trước hành động tạo order để bạn xác nhận.</p>
              )}
            </div>
            <button type="button" disabled={loading || prerequisitesLoading} onClick={start}
              aria-describedby={startBlockers.length ? 'autopilot-start-requirements' : undefined}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-brand-500 px-6 text-sm font-bold text-white shadow-sm hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
              Bắt đầu Autopilot
            </button>
            {startBlockers.length > 0 && <span id="autopilot-start-requirements" className="sr-only">Cần hoàn tất {startBlockers.join(' và ')}</span>}
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
              {['failed', 'cancelled'].includes(run.status) && (
                <button onClick={() => { setRun(null); onOpenBrief?.() }} disabled={loading}
                  className="inline-flex items-center gap-1 rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-2 text-[11px] font-bold text-brand-700 hover:bg-brand-100">
                  Chỉnh dữ liệu & chạy lại
                </button>
              )}
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
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-black uppercase tracking-wide text-slate-500">Tiến độ thực thi</p>
                <p className="mt-1 text-[11px] text-slate-500">5 giai đoạn · {orderedTasks.length} bước theo đúng thứ tự thực thi</p>
              </div>
              <ListChecks className="h-5 w-5 text-brand-500" />
            </div>
            <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              {executionStages.map((stage, index) => (
                <li key={stage.label} className={`rounded-xl border p-3 ${taskStatusClass(stage.status)}`}>
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-current/20 bg-white/70 text-[10px] font-black">{index + 1}</span>
                    <p className="text-[11px] font-bold leading-4">{stage.label}</p>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[10px] font-semibold opacity-80">
                    <span>{stage.done}/{stage.tasks.length} bước</span>
                    <span className="inline-flex items-center gap-1">{taskIcon(stage.status)} {stage.status === 'succeeded' ? 'Hoàn tất' : stage.status === 'pending' ? 'Chưa chạy' : RUN_LABELS[stage.status] || stage.status}</span>
                  </div>
                </li>
              ))}
            </ol>
            <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2">
              <summary className="cursor-pointer text-[11px] font-bold text-slate-700">Xem toàn bộ {orderedTasks.length} bước theo thứ tự</summary>
              <ol className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {orderedTasks.map((task, index) => (
                  <li key={task.task_id} title={task.error || task.result?.message || TASK_LABELS[task.key]}
                    className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 text-[11px] font-medium ${taskStatusClass(task.status)}`}>
                    <span className="w-5 shrink-0 text-right font-black opacity-60">{index + 1}</span>
                    {taskIcon(task.status)}
                    <span>{TASK_LABELS[task.key] || task.key}</span>
                  </li>
                ))}
              </ol>
            </details>
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
            selectionHint={strategySelectionHint}
            onSelect={chooseStrategy}
          />

          {(formatPlan?.formats?.length > 0 || creativeFiles.length > 0) && (
            <section className="rounded-2xl border border-brand-100 bg-white p-4 shadow-sm" aria-label="Kế hoạch định dạng creative">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-brand-700">Kế hoạch creative theo placement</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    Agent gộp các placement cùng kích thước và chỉ chuẩn bị tối đa {formatPlan?.max_assets || creativeFiles.length} asset cần thiết.
                  </p>
                </div>
                <span className="rounded-full bg-brand-50 px-2.5 py-1 text-[10px] font-bold text-brand-700">
                  {formatPlan?.source === 'ai_generate' ? `${formatPlan.estimated_provider_calls || 0} lượt tạo AI` : 'Dùng file tải lên'}
                </span>
              </div>
              {formatPlan?.formats?.length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {formatPlan.formats.map(item => (
                  <div key={item.format_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <p className="text-xs font-bold text-slate-800">{item.width} × {item.height}</p>
                    <p className="mt-0.5 truncate text-[10px] text-slate-500" title={item.format_id}>{item.format_id}</p>
                    <p className="mt-1 text-[10px] font-semibold text-brand-700">Phủ {item.zone_ids?.length || 0} placement</p>
                  </div>
                ))}
              </div>}
              {(formatPlan?.unsupported_zone_ids?.length > 0 || formatPlan?.omitted_by_cost_cap_zone_ids?.length > 0) && (
                <p className="mt-3 text-[11px] leading-5 text-amber-700">
                  {formatPlan.unsupported_zone_ids?.length || 0} placement chưa có format hỗ trợ; {formatPlan.omitted_by_cost_cap_zone_ids?.length || 0} placement ngoài giới hạn chi phí.
                </p>
              )}
              {creativeFiles.length > 0 && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <div className="flex items-center gap-2">
                    <ImageIcon className="h-4 w-4 text-brand-500" />
                    <p className="text-xs font-black text-slate-900">Creative đã tạo ({creativeFiles.length})</p>
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {creativeFiles.map((file, index) => (
                      <article key={file.id || file.url || index} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                        <div className="flex h-40 items-center justify-center bg-[linear-gradient(45deg,#f8fafc_25%,transparent_25%),linear-gradient(-45deg,#f8fafc_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f8fafc_75%),linear-gradient(-45deg,transparent_75%,#f8fafc_75%)] bg-[length:16px_16px] bg-[position:0_0,0_8px,8px_-8px,-8px_0px] p-2">
                          {file.url ? <img src={file.url} alt={`Creative ${file.formatId || index + 1}`} loading="lazy" className="max-h-full max-w-full object-contain" /> : <ImageIcon className="h-8 w-8 text-slate-300" />}
                        </div>
                        <div className="p-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate text-xs font-bold text-slate-900" title={file.name}>{file.formatId || file.name || `Creative ${index + 1}`}</p>
                              <p className="mt-0.5 text-[10px] text-slate-500">{file.width || '—'} × {file.height || '—'} · {file.intendedFormat || 'banner'}</p>
                            </div>
                            <span className="rounded-full bg-green-50 px-2 py-0.5 text-[9px] font-bold text-green-700">{taskByKey.analyze_creatives?.status === 'succeeded' ? 'Đã phân tích' : 'Đã tạo'}</span>
                          </div>
                          <p className="mt-2 text-[10px] text-slate-500">Phủ {creativeCoverage[index]?.length || 0} placement · {file.generation?.model || 'file tải lên'}</p>
                          {file.url && <a href={file.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-brand-700 hover:underline">Mở ảnh gốc <ExternalLink className="h-3 w-3" /></a>}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {run.status === 'completed' && orderResult ? (
            <AutopilotOutcome
              workspace={workspaceSnapshot}
              taskByKey={taskByKey}
              fallbackBrief={displayBrief}
              reportState={reportState}
              onReportChange={onReportChange}
              onSendReportQuestion={onSendReportQuestion}
              onReportActivate={onReportActivate}
              onReportExit={onReportExit}
            />
          ) : <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm" aria-labelledby="autopilot-results-title">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-brand-600">Kết quả theo thời gian thực</p>
                <h3 id="autopilot-results-title" className="mt-1 text-sm font-black text-slate-900">Kết quả Autopilot</h3>
                <p className="mt-1 text-xs text-slate-500">Tóm tắt các đầu ra có thể kiểm tra, thay cho log kỹ thuật của từng tool.</p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${taskByKey.run_order_guard?.result?.passed ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                Guard {taskByKey.run_order_guard?.result?.passed ? 'đã đạt' : 'chưa chạy'}
              </span>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Audience</p>
                <p className="mt-1 text-lg font-black text-slate-900">{audienceResult.attrs?.length || 0} segment</p>
                <p className="mt-1 text-[10px] leading-4 text-slate-500">
                  {audienceCatalogCount ? `${audienceCatalogCount} catalog` : 'Catalog hiện hành'} → {audienceResult.retrieval?.candidates || audienceResult.retrieval?.candidate_count || audienceResult.retrieval?.retrieval_candidates || 0} ứng viên RAG · {audienceResult.retrieval?.reranked ? 'đã rerank' : 'selector an toàn'}
                </p>
              </article>
              <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Placement</p>
                <p className="mt-1 text-lg font-black text-slate-900">{placementResult.selectedZoneIds?.length || 0} vị trí</p>
                <p className="mt-1 text-[10px] leading-4 text-slate-500">Đã lọc theo inventory, conflict và kích thước creative.</p>
              </article>
              <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Dự báo</p>
                <p className="mt-1 text-lg font-black text-slate-900">{formatNumber(forecastResult.estimated_reach)} người</p>
                <p className="mt-1 text-[10px] leading-4 text-slate-500">{formatNumber(forecastResult.estimated_impressions)} lượt hiển thị · CPM {formatNumber(forecastResult.average_cpm)} ₫</p>
              </article>
              <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Order</p>
                <p className="mt-1 text-lg font-black text-slate-900">{orderResult?.id || orderResult?._id || 'Chưa tạo'}</p>
                <p className={`mt-1 text-[10px] font-bold ${orderResult?.status === 'active' ? 'text-green-700' : orderResult?.status === 'pending' ? 'text-amber-700' : 'text-slate-500'}`}>Trạng thái: {orderResult?.status || '—'}</p>
              </article>
            </div>

            {(audienceResult.attrs?.length > 0 || forecastResult.calculation) && (
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {audienceResult.attrs?.length > 0 && (
                  <details open className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <summary className="cursor-pointer text-xs font-black text-slate-900">
                      Audience đã chọn · {audienceResult.attrs.length} segment
                    </summary>
                    <p className="mt-1 text-[10px] leading-4 text-slate-500">
                      {audienceCatalogCount ? `Catalog có ${audienceCatalogCount} segment.` : 'Run cũ chưa lưu tổng số catalog.'} RAG truy xuất {audienceResult.retrieval?.candidates || audienceResult.retrieval?.candidate_count || 0} ứng viên liên quan trước khi selector an toàn chọn kết quả cuối.
                    </p>
                    <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                      {audienceResult.attrs.map((item, index) => (
                        <li key={item._id || item.code || index} className="rounded-lg bg-slate-50 px-2.5 py-2">
                          <p className="text-[11px] font-bold text-slate-900">{audienceName(item)}</p>
                          {(item.reason || item.description) && <p className="mt-0.5 line-clamp-2 text-[10px] leading-4 text-slate-500">{item.reason || item.description}</p>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}

                {forecastResult.calculation && (
                  <details open className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <summary className="cursor-pointer text-xs font-black text-slate-900">Nguồn của dự báo reach & chi phí</summary>
                    <dl className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                      <div className="rounded-lg bg-slate-50 p-2"><dt className="text-slate-500">Ngân sách</dt><dd className="font-bold text-slate-900">{formatNumber(forecastResult.budget_vnd)} ₫</dd></div>
                      <div className="rounded-lg bg-slate-50 p-2"><dt className="text-slate-500">CPM catalog có trọng số</dt><dd className="font-bold text-slate-900">{formatNumber(forecastResult.average_cpm)} ₫</dd></div>
                      <div className="rounded-lg bg-slate-50 p-2"><dt className="text-slate-500">Tần suất chiến lược</dt><dd className="font-bold text-slate-900">{forecastResult.frequency || '—'}</dd></div>
                      <div className="rounded-lg bg-slate-50 p-2"><dt className="text-slate-500">Trần reach inventory</dt><dd className="font-bold text-slate-900">{formatNumber(forecastResult.inventory_reach_cap)}</dd></div>
                    </dl>
                    <p className="mt-3 text-[10px] leading-4 text-slate-500">
                      Impression = ngân sách ÷ CPM × 1.000. Reach = giá trị nhỏ hơn giữa trần inventory và impression ÷ tần suất. Đây là forecast, không phải số liệu delivery.
                    </p>
                  </details>
                )}
              </div>
            )}

            {orderResult?.status === 'pending' && (
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">
                Order đang chờ kích hoạt nên test site chưa hiển thị quảng cáo. Đây là trạng thái an toàn sau khi tạo order, không phải lỗi creative.
              </div>
            )}

            {orderResult?.warnings?.length > 0 && (
              <details className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-800">
                <summary className="cursor-pointer font-bold">{orderResult.warnings.length} cảnh báo cấu hình cần kiểm tra</summary>
                <ul className="mt-2 list-disc space-y-1 pl-4">
                  {orderResult.warnings.map((warning, index) => <li key={`${warning}:${index}`}>{warning}</li>)}
                </ul>
              </details>
            )}

            {placementLinks.length > 0 && (
              <div className="mt-4 border-t border-slate-100 pt-4">
                <p className="text-xs font-bold text-slate-900">Trang test theo placement</p>
                <p className="mt-1 text-[11px] text-slate-500">Mở để kiểm tra vị trí. Quảng cáo chỉ xuất hiện khi order ở trạng thái active và site đang dùng cùng backend.</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {placementLinks.map(zone => (
                    <a key={zone.siteUrl} href={zone.siteUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-[11px] font-bold text-brand-700 hover:bg-brand-100">
                      {zone.channel || zone.siteId || 'Test site'} <ExternalLink className="h-3 w-3" />
                    </a>
                  ))}
                  <a href={`${ADSPILOT_URL}/#/orders`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-bold text-slate-700 hover:border-brand-200 hover:text-brand-700">
                    Quản lý order trên AdsPilot <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            )}

            <details className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-3">
              <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-bold text-slate-700">
                <Activity className="h-4 w-4 text-brand-500" /> Chi tiết kỹ thuật
                <span className="font-normal text-slate-500">trace · RAG/rerank · guard · idempotency</span>
              </summary>
              <div className="mt-2 space-y-1.5 text-[11px]">
                <p className="rounded-lg bg-white px-2 py-1.5 text-slate-600"><span className="font-bold text-slate-800">Run trace:</span> {run.trace_id || run.run_id}</p>
                {evidenceRows.length ? evidenceRows.map(row => (
                  <p key={row.key} className="rounded-lg bg-white px-2 py-1.5 text-slate-600">
                    <span className="font-bold text-slate-800">{row.task}:</span> {evidenceText(row.evidence)}
                  </p>
                )) : <p className="px-2 py-1 text-slate-500">Chi tiết sẽ xuất hiện khi các tác vụ hoàn tất.</p>}
              </div>
            </details>
          </section>}

          {waiting && (
            <AutopilotReview
              task={waiting}
              label={TASK_LABELS[waiting.key] || waiting.key}
              brief={displayBrief}
              formatPlan={formatPlan}
              selectedPlacementIds={placementSelection}
              onPlacementSelectionChange={waiting.key === 'plan_placement_intent' ? setPlacementSelection : undefined}
            />
          )}

          {waiting && (
            <div className="sticky bottom-2 z-10 flex flex-col gap-3 rounded-2xl border border-amber-300 bg-amber-50/95 p-3 shadow-[0_12px_36px_rgba(120,80,0,0.18)] backdrop-blur-md sm:flex-row sm:items-center">
              <ShieldCheck className="h-5 w-5 shrink-0 text-amber-700" />
              <div className="flex-1">
                <p className="text-xs font-bold text-amber-900">Cần bạn review: {TASK_LABELS[waiting.key]}</p>
                <p className="mt-0.5 text-xs text-amber-800">{waitingMessage}</p>
                <a href="#autopilot-review-artifact" className="mt-1 inline-block text-[11px] font-bold text-amber-900 underline underline-offset-2">Xem nội dung cần review ngay phía trên</a>
                {briefRetry && !retryReady && (
                  <p className="mt-1 text-[11px] font-semibold text-amber-900">
                    {pendingBrief ? 'Duyệt hoặc hủy đề xuất Brief trong Chat trước.' : `Sửa Brief trước khi kiểm tra lại: ${briefErrors.join(', ')}.`}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {briefRetry && pendingBrief && <button onClick={onOpenChat} className="rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900">Mở Chat để duyệt</button>}
                {waitingEdits.map(edit => edit.action && (
                  <button key={edit.label} onClick={() => openEditor(edit.action)} disabled={loading} className="rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100">{edit.label}</button>
                ))}
                <button onClick={cancelRunWithConfirmation} disabled={loading} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-red-200 hover:bg-red-50 hover:text-red-700">Hủy run</button>
                <button onClick={() => review(waiting, true)} disabled={loading || (retryAction && !retryReady) || (waiting.key === 'plan_placement_intent' && !placementSelection.length)} className={`rounded-lg px-3 py-1.5 text-xs font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300 ${waiting.key === 'launch_approval' ? 'bg-red-600 hover:bg-red-700' : 'bg-brand-500 hover:bg-brand-600'}`}>
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
