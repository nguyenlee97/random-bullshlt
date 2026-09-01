import { useCallback, useEffect, useRef, useState } from 'react'
import { AgentAPI } from '@/api/agentApi'
import { HypothesisEvidence, investigationControl } from './InvestigationEvidence'

const fmt = value => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(Number(value || 0))
const totals = rows => (rows || []).reduce((sum, row) => {
  for (const key of Object.keys(sum)) sum[key] += Number(row[key] || 0)
  return sum
}, { impressions: 0, clicks: 0, spend: 0 })
const inputClass = 'mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm'
const buttonClass = 'rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold disabled:opacity-40'
const assessmentLabel = {
  insufficient_evidence: 'Chưa đủ bằng chứng', ambiguous: 'Còn nhiều giả thuyết',
  supported_hypothesis: 'Giả thuyết có bằng chứng', unsupported: 'Chưa hỗ trợ',
}
const healthLabel = { healthy: 'Ổn định', bad: 'Cần xử lý', watch: 'Cần theo dõi', not_evaluated: 'Chưa đánh giá' }
const causeLabel = { supported_hypothesis: 'Có bằng chứng hỗ trợ giả thuyết nguyên nhân', unresolved: 'Chưa chốt nguyên nhân', insufficient_evidence: 'Thiếu bằng chứng về nguyên nhân' }
const scopeLabel = { isolated_document: 'Tài liệu thử nghiệm cô lập', creative_metadata: 'Metadata creative/catalog', baseline_order_comparison: 'Order so với report baseline', catalog_benchmark: 'Benchmark catalog và creative metadata', report_measurement: 'Độ đầy đủ report', measured_click_gap: 'Khoảng trống click đo được', unknown: 'Chưa xác định' }
export const analyticsUrl = campaignId => {
  const base = import.meta.env.VITE_ANALYTICS_URL || (location.hostname === 'localhost' || location.hostname === '127.0.0.1'
    ? 'http://localhost:5174/' : 'https://analytics.pawgrammers.io.vn/')
  const url = new URL(base, location.href)
  url.searchParams.set('campaignId', campaignId)
  return url.href
}

export function ScenarioLab({ campaignId, onApplied, onBusy }) {
  const [workspace, setWorkspace] = useState(null)
  const [form, setForm] = useState({ presetId: 'low_impression_zone', targetPlacementId: '', windowDays: 3, persistenceWindows: 2, impact: 0.75, seed: 'default' })
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  const request = useRef(null)
  const load = useCallback(async () => {
    if (campaignId) setWorkspace(await AgentAPI.getCampaignScenarios(campaignId))
  }, [campaignId])
  useEffect(() => { load().catch(reason => setError(reason.message)) }, [load])
  const change = updates => { setForm(value => ({ ...value, ...updates })); setPreview(null); request.current = null }
  const execute = async mode => {
    setBusy(true); onBusy?.(true); setError('')
    try {
      if (mode === 'preview') {
        setPreview(await AgentAPI.previewCampaignScenario(campaignId, form))
        request.current = null
      } else {
        if (!preview) throw new Error('Hãy xem trước dữ liệu trước khi áp dụng.')
        request.current ||= { ...form, expectedRevision: preview.activeRevision, requestId: crypto.randomUUID() }
        const result = await AgentAPI.applyCampaignScenario(campaignId, request.current)
        setReceipt(result); setPreview(null); request.current = null
        onApplied?.(result)
        await load()
      }
    } catch (reason) {
      setError(reason.message)
      if (reason.status === 409) { setPreview(null); request.current = null; await load().catch(() => {}) }
    } finally { setBusy(false); onBusy?.(false) }
  }
  const before = totals(preview?.beforeRecords), after = totals(preview?.records)
  const selectedPreset = workspace?.presets?.find(item => item.id === form.presetId)
  const expectation = selectedPreset?.expectation
  return <section className="space-y-5 bg-white p-5 text-slate-900">
    <div><p className="text-xs font-semibold uppercase tracking-wider text-violet-600">Report Scenario Lab</p>
      <h1 className="mt-1 text-xl font-bold">Giả lập tình huống campaign</h1>
      <p className="mt-2 text-sm text-slate-600">{campaignId} · revision hiện tại {workspace?.state?.activeRevision ?? '—'}</p>
      <p className="mt-1 text-xs text-slate-500">Thay đổi dữ liệu report để thử Evaluation. Không thay đổi order hoặc ngân sách campaign.</p></div>
    {error && <div role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}<button className="ml-2 underline" onClick={() => load().then(() => setError('')).catch(e => setError(e.message))}>Tải lại</button>
      <a className="ml-3 underline" href="/manage" target="_blank" rel="noreferrer">Mở Agent để đăng nhập</a></div>}
    <fieldset disabled={busy || !workspace} className="grid gap-4 sm:grid-cols-2 disabled:opacity-60">
      <label className="text-sm font-medium">Tình huống<select className={inputClass} value={form.presetId} onChange={e => change({ presetId: e.target.value })}>
        {(workspace?.presets || []).map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
      <label className="text-sm font-medium">Placement<select className={inputClass} value={form.targetPlacementId} onChange={e => change({ targetPlacementId: e.target.value })}>
        <option value="">Tự chọn placement có nhiều impression nhất</option>{workspace?.placements?.map(id => <option key={id}>{id}</option>)}</select></label>
      <label className="text-sm font-medium">Số ngày mỗi kỳ<input className={inputClass} type="number" min="1" max="30" value={form.windowDays} onChange={e => change({ windowDays: Number(e.target.value) })} /></label>
      <label className="text-sm font-medium">Số kỳ bị ảnh hưởng<input className={inputClass} type="number" min="1" max="10" value={form.persistenceWindows} onChange={e => change({ persistenceWindows: Number(e.target.value) })} /></label>
      <label className="text-sm font-medium">Mức ảnh hưởng: {Math.round(form.impact * 100)}%<input className="mt-3 w-full" type="range" min="0" max="1" step=".05" value={form.impact} onChange={e => change({ impact: Number(e.target.value) })} /></label>
      <label className="text-sm font-medium">Seed / mã thử nghiệm<input className={inputClass} maxLength="100" value={form.seed} onChange={e => change({ seed: e.target.value })} /></label>
    </fieldset>
    <p className="text-xs text-slate-500">Mỗi lần preview đều bắt đầu từ baseline; không cộng dồn scenario. Một số preset kỹ thuật dùng mức ảnh hưởng cố định.</p>
    {expectation && <section aria-label="Kỳ vọng kiểm thử scenario" className="space-y-3 rounded-xl border border-violet-200 bg-violet-50/50 p-4 text-sm">
      <div><h2 className="font-bold text-violet-950">Kỳ vọng kiểm thử</h2><p className="mt-1 text-xs text-violet-900">Minimum contract theo policy mặc định; thay đổi impact/window có thể làm tín hiệu không đủ threshold.</p></div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="min-w-0"><p className="text-xs font-semibold uppercase text-slate-500">L1 incidents</p><p className="break-words">{expectation.l1IssueTypes?.join(', ') || 'Không mở incident mới'}</p></div>
        <div className="min-w-0"><p className="text-xs font-semibold uppercase text-slate-500">L2 hypotheses</p><p className="break-words">{expectation.l2Hypotheses?.join(', ') || 'Không cần chẩn đoán mới'}</p></div>
        <div className="min-w-0"><p className="text-xs font-semibold uppercase text-slate-500">Evidence cần có</p><p className="break-words">{expectation.requiredEvidence?.join(', ') || '—'}</p></div>
      </div>
      <p className="text-xs text-slate-600">{expectation.note}</p>
    </section>}
    {preview && <div className="overflow-auto rounded-xl border"><table className="w-full text-left text-sm">
      <caption className="p-2 text-left font-semibold">Trước / sau · đang xem revision {preview.activeRevision}</caption>
      <thead className="bg-slate-50"><tr><th className="p-2">Chỉ số</th><th>Hiện tại</th><th>Sau apply</th></tr></thead>
      <tbody>{Object.keys(before).map(key => <tr key={key} className="border-t"><td className="p-2">{key}</td><td>{fmt(before[key])}</td><td>{fmt(after[key])}</td></tr>)}</tbody>
    </table></div>}
    <div className="flex flex-wrap gap-2">
      <button className={buttonClass} disabled={busy || !workspace} onClick={() => execute('preview')}>Xem trước</button>
      <button className={buttonClass + ' bg-violet-700 text-white'} disabled={busy || !preview} onClick={() => execute('apply')}>Áp dụng & chạy Evaluation</button>
      <button className={buttonClass} disabled={busy || !workspace} onClick={() => change({ presetId: 'healthy_baseline' })}>Chọn khôi phục baseline</button>
    </div>
    <p role="status" aria-live="polite" className="text-sm text-slate-600">{busy ? 'Đang xử lý; vui lòng giữ cửa sổ này mở…' : receipt ? 'Đã áp dụng revision ' + receipt.scenario.revision + '. Evaluation: ' + receipt.evaluation.status : ''}</p>
    {receipt?.acceptance && <div className={`rounded-lg p-3 text-sm ${receipt.acceptance.status === 'matched' ? 'bg-emerald-50 text-emerald-900' : receipt.acceptance.status === 'not_matched' ? 'bg-amber-50 text-amber-900' : 'bg-slate-100 text-slate-700'}`}>
      <strong>{receipt.acceptance.status === 'matched' ? 'L1 khớp minimum contract.' : receipt.acceptance.status === 'not_matched' ? 'L1 chưa khớp minimum contract.' : 'Chưa thể đối chiếu L1.'}</strong>
      <p className="mt-1 break-words">Quan sát: {receipt.acceptance.observed_issue_types?.join(', ') || 'không có incident mới'}.</p>
      {!!receipt.acceptance.missing_issue_types?.length && <p className="mt-1 break-words">Còn thiếu: {receipt.acceptance.missing_issue_types.join(', ')}.</p>}
      {!!receipt.acceptance.additional_issue_types?.length && <p className="mt-1 break-words">Tín hiệu bổ sung: {receipt.acceptance.additional_issue_types.join(', ')}.</p>}
    </div>}
    {receipt?.evaluation?.status === 'retryable' && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm">Dữ liệu đã được lưu. Evaluation cần chạy lại; không cần tạo lại scenario.</p>}
    <a className="inline-block text-sm font-semibold text-blue-700 underline" href={'/manage/campaigns/' + encodeURIComponent(campaignId)} target="_blank" rel="noreferrer">Xem incident và điều tra trong Agent</a>
    <details><summary className="cursor-pointer text-sm font-semibold">Lịch sử revision ({workspace?.revisions?.length || 0})</summary>
      <ul className="mt-3 space-y-2 text-xs">{workspace?.revisions?.map(r => <li key={r.revision} className="rounded-lg bg-slate-50 p-2">Revision {r.revision} · {r.scenario?.presetId || 'baseline'} · {r.status || 'ready'}{r.revision === workspace?.state?.activeRevision ? ' · đang dùng' : ''}</li>)}</ul>
    </details>
  </section>
}

export function InvestigationProgress({ job }) {
  const states = { queued: 'Chờ xử lý', running: 'Đang xử lý', completed: 'Hoàn tất', partial: 'Chưa đầy đủ', failed: 'Thất bại', interrupted: 'Bị gián đoạn', stale: 'Dữ liệu đã thay đổi' }
  const roles = { performance: 'Performance Analyst', creative: 'Creative Inspector', setup: 'Setup Auditor', placement: 'Placement Investigator', coordinator: 'Coordinator' }
  const phases = { model: 'Đang phân tích evidence', tool: 'Đang thu thập', reused: 'Dùng lại kết quả hợp lệ', starting: 'Bắt đầu', review: 'Kiểm tra kết luận' }
  const seconds = value => `${(Number(value || 0) / 1000).toFixed(1)}s`
  const tasks = Object.values(job.tasks || {})
  const completed = tasks.filter(task => task.status === 'completed').length
  const evidenceCount = tasks.reduce((sum, task) => sum + Object.keys(task.tool_evidence_ids || {}).length, 0)
  return <section aria-label="Tiến độ investigation" className="space-y-2 rounded-xl border border-violet-200 p-3">
    <div className="flex flex-wrap justify-between gap-2"><h4 className="text-sm font-bold">Nhóm điều tra L2</h4><p role="status" className="text-sm font-semibold">{states[job.status] || job.status}</p></div>
    <p className="break-all text-xs text-slate-500">{job.job_id}</p>
    <p className="text-xs text-slate-500">Revision {job.dataset_revision} · {job.model_calls || 0}/24 lượt model · lần xử lý {job.attempts || 0}/3</p>
    {!!tasks.length && <p className="text-xs font-semibold text-violet-900">{completed}/{tasks.length} vai trò hoàn tất · {evidenceCount} evidence đã gắn vào specialist</p>}
    <div className="grid gap-2 sm:grid-cols-2">{tasks.map(t => <div key={t.role} className="min-w-0 space-y-1 rounded-lg bg-slate-50 p-3 text-xs">
      <strong>{roles[t.role] || t.role} · {states[t.status] || t.status}</strong>
      <p>{phases[t.phase] || states[t.phase] || 'Chưa có tiến độ chi tiết'}{t.current_tool ? `: ${t.current_tool}` : ''}</p>
      <p className="break-words">Công cụ: {t.tool_calls?.join(', ') || 'Chưa gọi'}</p>
      {!!Object.keys(t.tool_evidence_ids || {}).length && <details><summary className="cursor-pointer text-slate-600">Evidence của specialist ({Object.keys(t.tool_evidence_ids).length})</summary>
        <ul className="mt-2 space-y-1">{Object.entries(t.tool_evidence_ids).map(([tool, evidenceId]) => <li className="break-all" key={tool}><strong>{tool}</strong> → {evidenceId}</li>)}</ul></details>}
      {!!t.reused_evidence_count && <p className="text-blue-800">Dùng lại {t.reused_evidence_count} evidence cùng snapshot; không gọi lại probe.</p>}
      {!!t.timings?.length && <details><summary className="cursor-pointer text-slate-600">Thời gian / retry ({t.timings.length})</summary>
        <ul className="mt-2 space-y-1">{t.timings.map((event, index) => <li key={index} className="break-words">{event.kind === 'model' ? 'Model' : event.tool} · {states[event.status] || (event.status === 'unavailable' ? 'Không có evidence' : event.status)} · {event.duration_ms === undefined ? 'Đang chạy' : seconds(event.duration_ms)} · lần {event.attempt}{event.error_code ? ` · ${event.error_code}` : ''}</li>)}</ul></details>}
      {t.result?.summary && <p className="mt-1">{t.result.summary}</p>}{t.error && <p className="text-rose-700">{t.error}</p>}
      {t.error_code && <p className="text-rose-700">Mã lỗi: {t.error_code}</p>}
      {!!t.validation_errors?.length && <p className="text-amber-800">Lịch sử lỗi: {t.validation_errors.map(e => `${e.code}${e.attempt ? ` (lần ${e.attempt})` : ''}`).join(', ')} · lần xử lý này đã dùng {t.repairs_used || 0}/1 lượt sửa hoặc retry.</p>}
    </div>)}</div>
    {job.review?.summary && <p className="text-sm">Coordinator: {job.review.summary}</p>}
    {job.error && <p role="alert" className="text-xs text-amber-800">{job.error}</p>}
    {['queued', 'running'].includes(job.status) && <p className="text-xs text-slate-500">Có thể rời trang; investigation tiếp tục chạy nền và tự cập nhật tại đây.</p>}
  </section>
}

function Investigation({ bundle }) {
  if (!bundle) return <p className="text-sm text-slate-500">Chưa có kết quả L2.</p>
  return <div className="space-y-3 rounded-xl bg-slate-50 p-4">
    <p className="font-semibold">{assessmentLabel[bundle.assessment] || bundle.assessment || 'Kết quả L2'}</p>
    {bundle.symptom_status === 'detected_by_l1' && <p className="text-sm">L1 đã phát hiện triệu chứng bất thường; đây chưa phải kết luận nguyên nhân.</p>}
    {bundle.cause_status && <p className="text-sm font-semibold">{causeLabel[bundle.cause_status] || bundle.cause_status}</p>}
    {bundle.claim_scope && <p className="text-xs text-slate-600">Phạm vi bằng chứng: {scopeLabel[bundle.claim_scope] || bundle.claim_scope}</p>}
    {bundle.partial && <p role="status" className="text-sm text-amber-800">Điều tra chưa đầy đủ — có specialist hoặc coordinator chưa hoàn tất.</p>}
    <p className="text-xs text-slate-500">Revision {bundle.dataset_revision} · {bundle.mode === 'multi_agent' ? 'Specialist + coordinator; giả thuyết dựa trên evidence, chưa chứng minh quan hệ nhân quả.' : 'Playbook deterministic; điểm trọng số luật, không phải xác suất nguyên nhân.'}</p>
    {bundle.summary && <p className="text-sm">{bundle.summary}</p>}
    {!!bundle.limitations?.length && <div className="text-xs text-amber-900"><strong>Giới hạn / chưa kiểm chứng</strong><ul className="mt-1 list-disc pl-4">{bundle.limitations.map((text, i) => <li key={i}>{text}</li>)}</ul></div>}
    {!!bundle.review?.evidence_ids?.length && <p className="text-xs">Dẫn chứng: {bundle.review.evidence_ids.join(', ')}</p>}
    {!!bundle.review?.contradictions?.length && <p className="text-xs text-amber-800">Cần làm rõ: {bundle.review.contradictions.join('; ')}</p>}
    {bundle.relationship_version === 'evidence-relations-v1' ? <HypothesisEvidence bundle={bundle} /> : <ol className="space-y-2">{bundle.hypotheses?.slice(0, 3).map(h => <li key={h.hypothesis_id} className="text-sm"><strong>{h.label}</strong> · {fmt(h.score_share)} điểm<p className="mt-1 text-xs text-slate-500">{h.explanation}</p></li>)}</ol>}
    <details><summary className="cursor-pointer text-sm">Bằng chứng và nguồn dữ liệu</summary>
      <ul className="mt-2 space-y-2">{bundle.probes?.map(p => <li className="text-xs" key={p.evidence_id || p.probe_id}><strong>{p.probe_id} · {p.status}</strong><p>{p.summary}</p><p className="text-slate-500">Nguồn: {p.source} · {p.evidence_id} · {p.observed_at}</p>
        {p.screenshot_base64 && <img className="mt-2 max-w-full rounded border" alt="Ảnh trang thử nghiệm được Chromium chụp khi điều tra" src={'data:image/png;base64,' + p.screenshot_base64} />}
        <pre className="mt-1 max-h-44 overflow-auto">{JSON.stringify(p.evidence, null, 2)}</pre></li>)}</ul>
    </details>
    {!!bundle.recovery_options?.length && <details><summary className="cursor-pointer text-sm">Phương án tham khảo — chưa thực thi</summary>{bundle.recovery_options.map(o => <p className="mt-2 text-xs" key={o.action_id}>{o.label} · rủi ro {o.risk}<br />Kiểm chứng: {o.verification_plan}</p>)}</details>}
  </div>
}

export function IncidentQuestions({ campaignId, incident, enabled }) {
  const [question, setQuestion] = useState(''), [answers, setAnswers] = useState([])
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const request = useRef(null), generation = useRef(0)
  const bundleId = incident.investigation?.bundle_id
  const scope = `${campaignId}:${incident.incident_id}:${incident.dataset_revision}:${bundleId}:${enabled}`
  const currentScope = useRef(scope)
  currentScope.current = scope
  useEffect(() => {
    const seq = ++generation.current
    setAnswers([]); setError(''); setBusy(false); request.current = null
    if (enabled) AgentAPI.getIncidentQuestions(campaignId, incident.incident_id)
      .then(r => { if (generation.current === seq) setAnswers(r.questions || []) })
      .catch(e => { if (generation.current === seq) setError(e.message) })
    return () => { generation.current++ }
  }, [campaignId, incident.incident_id, scope, enabled])
  const submit = async event => {
    event.preventDefault()
    if (!question.trim() || busy) return
    const seq = ++generation.current, submittedScope = scope
    setBusy(true); setError('')
    request.current ||= { question: question.trim(), requestId: crypto.randomUUID(), expectedRevision: incident.dataset_revision, expectedBundleId: bundleId }
    try {
      const result = await AgentAPI.askEvaluationIncident(campaignId, incident.incident_id, request.current)
      if (generation.current !== seq || currentScope.current !== submittedScope) return
      setAnswers(rows => [...rows.filter(r => r.question_id !== result.question_id), result].slice(-20))
      setQuestion(''); request.current = null
    } catch (e) {
      if (generation.current === seq && currentScope.current === submittedScope) setError(e.message)
    } finally { if (generation.current === seq && currentScope.current === submittedScope) setBusy(false) }
  }
  return <section aria-label={`Hỏi đáp ${incident.incident_id}`} className="space-y-3 rounded-xl border p-3">
    <h4 className="text-sm font-semibold">Hỏi về incident và evidence</h4>
    <p className="text-xs text-slate-500">Chỉ đọc, không duyệt hoặc thực thi recovery. Mỗi câu hỏi gắn với kết quả L2 hiện tại.</p>
    {answers.map(a => <div key={a.question_id} className="space-y-1 rounded-lg bg-slate-50 p-3 text-sm">
      <p className="font-semibold">{a.question}</p>
      <p className="text-xs text-slate-500">Revision {a.dataset_revision}{a.dataset_revision !== incident.dataset_revision || a.bundle_id !== bundleId ? ' · Kết quả lịch sử, không phải evidence hiện tại' : ''}</p>
      <p className="text-xs text-slate-500">{assessmentLabel[a.assessment] || a.assessment}</p>
      <p className="whitespace-pre-wrap">{a.answer}</p>
      {!!a.limitations?.length && <p className="text-xs text-amber-800">Giới hạn: {a.limitations.join(' ')}</p>}
      <ul className="text-xs text-slate-600">{a.citations.map(c => <li key={c.evidence_id}>{c.evidence_id} · {c.probe_id} · {c.source}</li>)}</ul>
      <p className="text-xs text-slate-500">{a.notice}</p>
    </div>)}
    <form onSubmit={submit} className="space-y-2">
      <label className="block text-sm">Câu hỏi cho {incident.incident_id}<textarea className={inputClass} rows={2} maxLength={1200} disabled={busy || !enabled} value={question}
        placeholder="Evidence nào cho thấy vùng click bị che? Còn thiếu bằng chứng gì?"
        onChange={e => { setQuestion(e.target.value); request.current = null }} /></label>
      <button className={buttonClass} disabled={busy || !enabled || !question.trim()} type="submit">{busy ? 'Đang đối chiếu evidence…' : 'Hỏi về evidence'}</button>
    </form>
    {!enabled && <p className="text-xs text-slate-500">Cần bật L2 multi-agent và có kết quả điều tra trước khi hỏi.</p>}
    {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
  </section>
}

export default function LiveEvaluationPanel({ campaignId }) {
  const [data, setData] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [histories, setHistories] = useState({})
  const currentCampaign = useRef(campaignId), requestSequence = useRef(0)
  currentCampaign.current = campaignId
  const load = useCallback(async () => {
    const sequence = ++requestSequence.current
    const result = await AgentAPI.getCampaignEvaluation(campaignId)
    if (currentCampaign.current === campaignId && sequence === requestSequence.current) { setData(result); setLoadError('') }
  }, [campaignId])
  useEffect(() => {
    setData(null); setHistories({}); setLoadError(''); setError('')
    let stopped = false, timer
    const refresh = () => load().catch(e => { if (!stopped) setLoadError(e.message) })
    const poll = async () => { await refresh(); if (!stopped) timer = setTimeout(poll, 3000) }
    poll(); window.addEventListener('focus', refresh)
    return () => { stopped = true; clearTimeout(timer); requestSequence.current++; window.removeEventListener('focus', refresh) }
  }, [load])
  const execute = async action => {
    setBusy(true); setError('')
    try { await action(); await load() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <div className="space-y-4">
    <section className="space-y-4 rounded-2xl border bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-bold">Live Evaluation</h2><a className="text-sm text-blue-700 underline" href={analyticsUrl(campaignId)} target="_blank" rel="noreferrer">Mở Scenario Lab trong Analytics</a></div>
      <p className="text-sm">Trạng thái: {healthLabel[data?.summary?.status] || data?.summary?.status || 'Đang tải…'} · {data?.summary?.open_count || 0} incident đang mở</p>
      {data && <fieldset disabled={busy} className="flex flex-wrap items-end gap-4">
        <label className="text-sm"><input type="checkbox" checked={data.policy.enabled} onChange={e => execute(() => AgentAPI.updateCampaignEvaluationPolicy(campaignId, { enabled: e.target.checked }))} /> Bật evaluation</label>
        <label className="text-sm">Mức quyền<select className={inputClass} value={data.policy.level} onChange={e => execute(() => AgentAPI.updateCampaignEvaluationPolicy(campaignId, { level: e.target.value }))}>
          <option value="L1">L1 — phát hiện</option><option value="L2">L2 — phát hiện + điều tra</option>{data.policy.level === 'L3' && <option value="L3">L3 cũ — executor bị khóa</option>}</select></label>
        <label className="text-sm">Chu kỳ (phút)<select className={inputClass} value={data.policy.schedule_minutes} onChange={e => execute(() => AgentAPI.updateCampaignEvaluationPolicy(campaignId, { schedule_minutes: Number(e.target.value) }))}>
          {[...new Set([5, 15, 30, 60, 360, 1440, data.policy.schedule_minutes])].sort((a, b) => a - b).map(minutes => <option key={minutes} value={minutes}>{minutes}</option>)}
        </select></label>
        <button className={buttonClass + ' bg-blue-700 text-white'} disabled={busy || !data.policy.enabled} onClick={() => execute(() => AgentAPI.runCampaignEvaluation(campaignId))}>Chạy đánh giá ngay</button>
      </fieldset>}
      <p className="text-xs text-slate-500">Lịch kiểm tra: {data?.policy?.schedule_minutes || 60} phút · worker {data?.worker_enabled ? 'được bật trong cấu hình' : 'chưa bật trong cấu hình'}. L3 chưa có executor an toàn.</p>
      <p className="text-xs text-slate-500">L2: {data?.investigation_mode === 'multi_agent' ? 'Multi-agent chạy nền' : 'Playbook deterministic — multi-agent chưa bật trong cấu hình'}.</p>
      {data?.investigation_error && <p role="alert" className="text-sm text-rose-700">{data.investigation_error}</p>}
      {loadError && <p role="alert" className="text-sm text-amber-800">Chưa cập nhật được tiến độ: {loadError}. Đang thử kết nối lại.</p>}
      {data?.last_run && <p className="text-xs">Lần chạy gần nhất: {data.last_run.status} · {data.last_run.completed_at || data.last_run.created_at} · {data.last_run.zalo_alerts || 0} yêu cầu enqueue Zalo (có chống trùng; chưa xác nhận đã nhận).</p>}
      {!!data?.last_run?.errors?.length && <div role="alert" className="rounded-lg bg-amber-50 p-3 text-xs">{data.last_run.errors.map((e, i) => <p key={i}>{e.stage}: {e.error}</p>)}</div>}
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
    </section>
    {(data?.incidents || []).map(i => { const control = investigationControl(i, data.investigation_jobs, data.policy.version, data.investigation_engine_version); return <article key={i.incident_id} className="min-w-0 space-y-4 rounded-2xl border bg-white p-5">
      <div><p className="text-xs text-slate-500">{i.incident_id} · {i.severity} · {i.state} · revision {i.dataset_revision}</p><h3 className="mt-1 font-bold">{i.title}</h3><p className="text-xs">{i.scope}</p></div>
      {(data.investigation_jobs || []).filter(job => job.incident_id === i.incident_id).slice(0, 3).map(job => <InvestigationProgress key={job.job_id} job={job} />)}
      <Investigation bundle={i.investigation} />
      <IncidentQuestions campaignId={campaignId} incident={i} enabled={data.investigation_mode === 'multi_agent' && data.policy.enabled && data.policy.level !== 'L1' && i.investigation?.mode === 'multi_agent'} />
      <details><summary className="cursor-pointer text-sm">Evidence L1 và timeline</summary><pre className="mt-2 max-h-56 overflow-auto text-xs">{JSON.stringify({ evidence: i.evidence, timeline: i.timeline }, null, 2)}</pre></details>
      <div className="flex flex-wrap gap-2">
        <button className={buttonClass} disabled={busy || control.disabled || !data.policy.enabled || data.policy.level === 'L1' || ['resolved', 'dismissed', 'false_positive'].includes(i.state)} onClick={() => execute(() => AgentAPI.actOnEvaluationIncident(campaignId, i.incident_id, 'investigate'))}>{control.label}</button>
        <button className={buttonClass} disabled={busy || ['resolved', 'dismissed'].includes(i.state)} onClick={() => execute(() => AgentAPI.actOnEvaluationIncident(campaignId, i.incident_id, 'dismiss'))}>Dismiss</button>
        <button className={buttonClass} disabled={busy} onClick={() => execute(async () => { const result = await AgentAPI.getEvaluationIncident(campaignId, i.incident_id); setHistories(h => ({ ...h, [i.incident_id]: result.history })) })}>Lịch sử điều tra</button>
      </div>
      {histories[i.incident_id]?.map(h => <details key={h.bundle_id}><summary className="cursor-pointer text-xs">{h.created_at} · revision {h.dataset_revision}</summary><Investigation bundle={h} /></details>)}
    </article>})}
    {data && !data.incidents.length && <p className="rounded-xl border border-dashed p-5 text-sm">Chưa có incident. Chạy evaluation hoặc chọn tình huống trong Analytics.</p>}
  </div>
}
