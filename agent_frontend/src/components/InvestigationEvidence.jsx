const statusLabels = {
  supported: 'Có quan sát hỗ trợ', contradicted: 'Có quan sát phản bác',
  conflicting: 'Bằng chứng mâu thuẫn', unknown: 'Chưa đủ bằng chứng',
}

export function hasTypedEvidence(bundle) {
  return ['evidence-relations-v1', 'evidence-relations-v2', 'evidence-relations-v3']
    .includes(bundle?.relationship_version)
}
const relationLabels = {
  supports: 'Hỗ trợ', contradicts: 'Phản bác trong phạm vi kiểm tra',
  context: 'Bối cảnh — không kết luận nguyên nhân', unavailable: 'Chưa kiểm chứng',
}
const scopeLabels = {
  isolated_document: 'Tài liệu thử nghiệm cô lập', creative_metadata: 'Metadata creative / catalog',
  baseline_order_comparison: 'Các trường order so với report baseline',
  catalog_benchmark: 'Benchmark catalog và creative metadata',
  report_measurement: 'Độ đầy đủ của report trong scope',
  measured_click_gap: 'Impression và click được ghi nhận trong report',
}
const palette = {
  supported: 'border-sky-200 bg-sky-50 text-sky-900',
  contradicted: 'border-slate-200 bg-slate-50 text-slate-700',
  conflicting: 'border-amber-200 bg-amber-50 text-amber-950',
  unknown: 'border-slate-200 bg-white text-slate-600',
}

export function EvidenceObservation({ evidence, relation }) {
  if (!evidence) return <p className="text-xs text-amber-800">Dẫn chứng không còn trong kết quả này. Hãy tải lại.</p>
  return <details className="min-w-0 rounded-lg border border-slate-200 bg-white p-3 text-xs">
    <summary className="cursor-pointer break-words font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600">
      {evidence.probe_id} · {relationLabels[relation] || evidence.status}
    </summary>
    <div className="mt-3 min-w-0 space-y-2 break-words">
      <p>{evidence.summary}</p>
      <dl className="space-y-1 text-slate-500">
        <div><dt className="inline font-medium">Nguồn: </dt><dd className="inline">{evidence.source}</dd></div>
        <div><dt className="inline font-medium">Thời điểm: </dt><dd className="inline">{evidence.observed_at || 'Không có'}</dd></div>
        <div><dt className="inline font-medium">Dẫn chứng: </dt><dd className="inline break-all">{evidence.evidence_id}</dd></div>
      </dl>
      {evidence.screenshot_base64 && <img className="max-w-full rounded-lg border" alt="Ảnh tài liệu cô lập được chụp khi thu thập bằng chứng" src={'data:image/png;base64,' + evidence.screenshot_base64} />}
      <pre className="max-h-56 max-w-full overflow-auto rounded bg-slate-50 p-2">{JSON.stringify(evidence.evidence, null, 2)}</pre>
    </div>
  </details>
}

export function HypothesisEvidence({ bundle }) {
  const observations = new Map((bundle.probes || []).map(item => [item.evidence_id, item]))
  return <section aria-label="Giả thuyết và bằng chứng" className="min-w-0 space-y-3">
    <div><h4 className="text-sm font-bold text-slate-900">Giả thuyết và bằng chứng</h4>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">Mỗi giả thuyết được kiểm tra độc lập. Phản bác overlay không loại trừ lỗi metadata. Các trạng thái dưới đây không phải xác suất nguyên nhân.</p></div>
    <div className="grid min-w-0 gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))' }}>{(bundle.hypotheses || []).map(h => {
      const direct = (h.evidence_links || []).filter(link => link.relation === 'supports' || link.relation === 'contradicts')
      const context = (h.evidence_links || []).filter(link => !direct.includes(link))
      return <article key={h.hypothesis_id} aria-label={h.label} className="min-w-0 space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="space-y-2"><h5 className="font-semibold text-slate-900">{h.label}</h5>
          <span className={`inline-block rounded-lg border px-2 py-1 text-xs font-medium ${palette[h.status] || palette.unknown}`}>{statusLabels[h.status] || 'Chưa kiểm tra'}</span>
          <p className="text-xs text-slate-500">{scopeLabels[h.claim_scope] || h.claim_scope}</p></div>
        <p className="text-xs leading-relaxed text-slate-600">{h.explanation}</p>
        <p className="text-xs font-medium">{h.supporting_evidence_ids?.length || 0} hỗ trợ · {h.contradicting_evidence_ids?.length || 0} phản bác</p>
        {direct.map(link => <EvidenceObservation key={link.evidence_id} evidence={observations.get(link.evidence_id)} relation={link.relation} />)}
        {!!h.missing_evidence?.length && <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900"><strong>Cần kiểm tra tiếp</strong>
          <ul className="mt-1 space-y-1">{h.missing_evidence.map(text => <li key={text}>{text}</li>)}</ul></div>}
        {!!context.length && <details className="text-xs text-slate-600"><summary className="cursor-pointer font-medium">Bối cảnh / chưa kiểm chứng ({context.length})</summary>
          <div className="mt-2 space-y-2">{context.map(link => <EvidenceObservation key={link.evidence_id} evidence={observations.get(link.evidence_id)} relation={link.relation} />)}</div></details>}
        <p className="border-t pt-3 text-xs leading-relaxed text-slate-500">{h.limitations?.join(' ')}</p>
      </article>
    })}</div>
  </section>
}

export function investigationControl(incident, jobs, policyVersion, engineVersion) {
  const job = (jobs || []).find(item => item.incident_id === incident.incident_id
    && item.dataset_revision === incident.dataset_revision && item.policy_version === policyVersion
    && (!engineVersion || item.engine_version === engineVersion))
  if (!job) return { label: 'Điều tra L2', disabled: false }
  if (['queued', 'running'].includes(job.status)) return { label: 'L2 đang chạy nền', disabled: true }
  if (['partial', 'failed', 'stale'].includes(job.status)) {
    const exhausted = job.model_calls >= 24 || job.attempts >= 3
    return { label: exhausted ? 'Đã hết lượt điều tra' : 'Tiếp tục điều tra', disabled: exhausted }
  }
  if (job.status === 'completed') return { label: 'L2 đã hoàn tất revision này', disabled: true }
  return { label: 'Điều tra L2', disabled: false }
}
