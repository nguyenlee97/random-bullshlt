import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, Check, Circle, Loader2, Pause, Play, RotateCw,
  ShieldCheck, Sparkles, Square, X,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'

const POLICY_OPTIONS = [
  { value: 'critical_only', label: 'Duyệt các bước quan trọng', note: 'Khuyến nghị' },
  { value: 'review_every_stage', label: 'Duyệt từng giai đoạn', note: 'Kiểm soát tối đa' },
  { value: 'auto_build_draft', label: 'Tự xây dựng bản nháp', note: 'Dừng trước launch' },
]

const TASK_LABELS = {
  normalize_brief: 'Chuẩn hóa brief', validate_brief: 'Kiểm tra brief',
  generate_strategy: 'Xây dựng chiến lược', retrieve_audience: 'Tìm audience',
  derive_targeting: 'Thiết lập targeting', analyze_creatives: 'Phân tích creative',
  rank_placements: 'Xếp hạng placements', assign_creatives: 'Gán creative',
  forecast: 'Dự báo reach & chi phí', build_order_draft: 'Tạo order draft',
  run_order_guard: 'Kiểm tra an toàn', launch_approval: 'Duyệt launch',
  create_order: 'Tạo order', verify_order: 'Xác minh order',
  create_setup_report: 'Tạo báo cáo setup',
}

const ARTIFACT_LABELS = {
  brief: 'brief', strategy: 'chiến lược', audience: 'audience',
  targeting: 'targeting', creative: 'creative', creative_verdict: 'creative verdict',
  placements: 'placements', assignments: 'phân bổ creative', forecast: 'dự báo',
  order_draft: 'order draft', order: 'order', report: 'báo cáo',
}

const taskIcon = status => {
  if (status === 'succeeded') return <Check className="h-3 w-3" />
  if (status === 'running') return <Loader2 className="h-3 w-3 animate-spin" />
  if (status === 'waiting_review') return <AlertTriangle className="h-3 w-3" />
  if (['failed', 'cancelled'].includes(status)) return <X className="h-3 w-3" />
  return <Circle className="h-2.5 w-2.5" />
}

export default function AutopilotPanel({ brief, onWorkspaceRefresh, onOpenCreative }) {
  const [policy, setPolicy] = useState('critical_only')
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    if (!run?.run_id) return
    const current = await AgentAPI.getAutopilotRun(run.run_id)
    if (current) {
      setRun(current)
      await onWorkspaceRefresh?.()
    }
  }, [run?.run_id, onWorkspaceRefresh])

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
      const committed = await AgentAPI.commitWorkspace('brief', brief)
      if (!committed?.ok) throw new Error('Không thể lưu brief trước khi chạy Autopilot.')
      const created = await AgentAPI.startAutopilot(policy)
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
    if (task.result?.reason === 'missing_creative') onOpenCreative?.()
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

  const progress = useMemo(() => {
    if (!run?.tasks?.length) return 0
    const done = run.tasks.filter(task => ['succeeded', 'skipped'].includes(task.status)).length
    return Math.round(done / run.tasks.length * 100)
  }, [run])

  const waiting = run?.tasks?.find(task => task.status === 'waiting_review')
  const missingBriefFields = useMemo(() => [
    !String(brief?.brand || '').trim() && 'thương hiệu',
    !(Number(brief?.budget) > 0) && 'ngân sách',
    !brief?.startDate && 'ngày bắt đầu',
    !brief?.endDate && 'ngày kết thúc',
  ].filter(Boolean), [brief])
  const briefReady = missingBriefFields.length === 0

  return (
    <section className="border-b border-brand-100 bg-white px-4 py-3 shadow-sm">
      {!run ? (
        <div className="mx-auto flex max-w-7xl flex-col gap-3 lg:flex-row lg:items-center">
          <div className="flex items-start gap-3 lg:min-w-[330px]">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Campaign Autopilot</h2>
              <p className="text-xs leading-5 text-slate-600">Điền brief ở workspace, chọn mức review rồi để Agent lập kế hoạch và thực hiện.</p>
            </div>
          </div>
          <div className="flex flex-1 flex-wrap gap-2">
            {POLICY_OPTIONS.map(item => (
              <button key={item.value} type="button" onClick={() => setPolicy(item.value)}
                className={`rounded-xl border px-3 py-2 text-left transition-colors ${policy === item.value ? 'border-brand-400 bg-brand-50 text-brand-800' : 'border-slate-200 bg-white text-slate-600 hover:border-brand-200'}`}>
                <span className="block text-xs font-semibold">{item.label}</span>
                <span className="block text-[10px] opacity-70">{item.note}</span>
              </button>
            ))}
          </div>
          <button type="button" disabled={!briefReady || loading} onClick={start}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-brand-500 px-5 text-sm font-bold text-white shadow-sm hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
            Bắt đầu Autopilot
          </button>
          {!briefReady && (
            <p className="w-full text-right text-[11px] text-amber-700 lg:w-auto">
              Còn thiếu: {missingBriefFields.join(', ')}
            </p>
          )}
        </div>
      ) : (
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-500" />
              <span className="text-sm font-bold text-slate-900">Campaign Autopilot</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">Plan v{run.plan_revision || 1}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${run.status === 'waiting_review' ? 'bg-amber-100 text-amber-800' : run.status === 'failed' ? 'bg-red-100 text-red-700' : run.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-brand-50 text-brand-700'}`}>{run.status}</span>
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

          <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
            {run.tasks.map(task => (
              <div key={task.task_id} title={task.error || task.result?.message || TASK_LABELS[task.key]}
                className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-medium ${task.status === 'succeeded' ? 'border-green-200 bg-green-50 text-green-700' : task.status === 'running' ? 'border-brand-300 bg-brand-50 text-brand-700' : task.status === 'waiting_review' ? 'border-amber-300 bg-amber-50 text-amber-800' : task.status === 'failed' ? 'border-red-200 bg-red-50 text-red-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
                {taskIcon(task.status)} {TASK_LABELS[task.key] || task.key}
              </div>
            ))}
          </div>

          {run.replan_blocked && (
            <div className="mt-3 rounded-xl border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
              <p className="font-bold">Run đã dừng an toàn sau khi order được tạo.</p>
              <p className="mt-0.5">Workspace có thay đổi mới. Hãy chọn “Cuộc trò chuyện mới” để tạo một run khác; Advertising Agent sẽ không tự tạo lại order.</p>
            </div>
          )}

          {run.last_replan && !run.replan_blocked && (
            <div className="mt-3 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-xs text-brand-800">
              <span className="font-bold">Kế hoạch đã được tính lại.</span>{' '}
              Thay đổi ở {run.last_replan.changed_artifacts.map(item => ARTIFACT_LABELS[item] || item).join(', ')} ảnh hưởng {run.last_replan.affected_tasks.length} tác vụ; các kết quả không liên quan được giữ nguyên.
            </div>
          )}

          {waiting && (
            <div className="mt-3 flex flex-col gap-3 rounded-xl border border-amber-300 bg-amber-50 p-3 sm:flex-row sm:items-center">
              <ShieldCheck className="h-5 w-5 shrink-0 text-amber-700" />
              <div className="flex-1">
                <p className="text-xs font-bold text-amber-900">Cần bạn review: {TASK_LABELS[waiting.key]}</p>
                <p className="mt-0.5 text-xs text-amber-800">{waiting.result?.message || (waiting.key === 'launch_approval' ? 'Kiểm tra bản order cuối cùng trước khi tạo chiến dịch.' : 'Kiểm tra bằng chứng và xác nhận để tiếp tục.')}</p>
              </div>
              <div className="flex gap-2">
                {waiting.result?.reason === 'missing_creative' && <button onClick={onOpenCreative} className="rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900">Mở Creative</button>}
                <button onClick={() => review(waiting, false)} disabled={loading} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700">Từ chối</button>
                <button onClick={() => review(waiting, true)} disabled={loading} className={`rounded-lg px-3 py-1.5 text-xs font-bold text-white ${waiting.key === 'launch_approval' ? 'bg-red-600 hover:bg-red-700' : 'bg-brand-500 hover:bg-brand-600'}`}>
                  {waiting.result?.review_action === 'retry' ? 'Đã xử lý, thử lại' : waiting.key === 'launch_approval' ? 'Duyệt & tạo order' : 'Duyệt & tiếp tục'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {error && <p className="mx-auto mt-2 max-w-7xl text-xs font-medium text-red-600">{error}</p>}
    </section>
  )
}
