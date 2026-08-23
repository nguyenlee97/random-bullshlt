import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, BellRing, CheckCircle2, FlaskConical,
  Play, RefreshCw, RotateCcw, ShieldCheck,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'

const severityTone = {
  critical: 'bg-rose-100 text-rose-700', high: 'bg-orange-100 text-orange-700',
  medium: 'bg-amber-100 text-amber-700', low: 'bg-blue-100 text-blue-700',
}

const total = records => (records || []).reduce((sum, row) => ({
  impressions: sum.impressions + Number(row.impressions || 0),
  clicks: sum.clicks + Number(row.clicks || 0),
  spend: sum.spend + Number(row.spend || 0),
}), { impressions: 0, clicks: 0, spend: 0 })

const number = value => new Intl.NumberFormat('vi-VN', {
  maximumFractionDigits: 1,
}).format(Number(value || 0))

export function ScenarioLab({ campaignId, onApplied }) {
  const [workspace, setWorkspace] = useState(null)
  const [form, setForm] = useState({
    presetId: 'low_impression_zone', targetPlacementId: '', windowDays: 3,
    persistenceWindows: 2, impact: 0.75, seed: 'default',
  })
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    if (!campaignId) return
    try { setWorkspace(await AgentAPI.getCampaignScenarios(campaignId)); setError('') }
    catch (reason) { setError(reason.message) }
  }, [campaignId])
  useEffect(() => { load() }, [load])
  const metrics = useMemo(() => total(preview?.records), [preview])

  const execute = async mode => {
    setBusy(mode); setError('')
    try {
      if (mode === 'preview') setPreview(await AgentAPI.previewCampaignScenario(campaignId, form))
      else {
        const result = await AgentAPI.applyCampaignScenario(campaignId, form)
        setPreview(null); await load(); onApplied?.(result)
      }
    } catch (reason) { setError(reason.message) }
    finally { setBusy('') }
  }

  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-start justify-between gap-3"><div className="flex gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-100 text-violet-700"><FlaskConical className="h-5 w-5" /></span><div><h3 className="font-black text-slate-950">Scenario Lab</h3><p className="mt-1 text-xs text-slate-500">Sửa facts, rebuild report và evaluation trên cùng một revision.</p></div></div><button type="button" onClick={load} className="rounded-lg border border-slate-200 p-2 text-slate-500"><RefreshCw className="h-4 w-4" /></button></div>
    <div className="mt-5 grid gap-4 md:grid-cols-2">
      <label className="text-xs font-bold text-slate-600">Scenario<select value={form.presetId} onChange={event => setForm(value => ({ ...value, presetId: event.target.value }))} className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm">{(workspace?.presets || []).map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <label className="text-xs font-bold text-slate-600">Placement ID<input value={form.targetPlacementId} onChange={event => setForm(value => ({ ...value, targetPlacementId: event.target.value }))} placeholder="Tự chọn zone lớn nhất" className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" /></label>
      <label className="text-xs font-bold text-slate-600">Window (ngày)<input type="number" min="1" max="30" value={form.windowDays} onChange={event => setForm(value => ({ ...value, windowDays: Number(event.target.value) }))} className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" /></label>
      <label className="text-xs font-bold text-slate-600">Impact {Math.round(form.impact * 100)}%<input type="range" min="0" max="1" step="0.05" value={form.impact} onChange={event => setForm(value => ({ ...value, impact: Number(event.target.value) }))} className="mt-3 w-full accent-violet-600" /></label>
    </div>
    {preview && <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-slate-50 p-3 text-center">{Object.entries(metrics).map(([key, value]) => <div key={key}><p className="text-[10px] font-bold uppercase text-slate-400">{key}</p><p className="mt-1 text-sm font-black text-slate-900">{number(value)}</p></div>)}</div>}
    {error && <p className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
    <div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={Boolean(busy)} onClick={() => execute('preview')} className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-black">Preview</button><button type="button" disabled={Boolean(busy)} onClick={() => execute('apply')} className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-xs font-black text-white"><Play className="h-4 w-4" /> Apply + run evaluation</button><button type="button" disabled={Boolean(busy)} onClick={() => setForm(value => ({ ...value, presetId: 'healthy_baseline' }))} className="inline-flex items-center gap-2 px-3 py-2.5 text-xs font-bold text-slate-500"><RotateCcw className="h-4 w-4" /> Baseline</button></div>
    {!!workspace?.revisions?.length && <div className="mt-4 border-t border-slate-100 pt-3"><p className="text-xs font-black text-slate-600">Revision history</p><div className="mt-2 space-y-1">{workspace.revisions.map(item => <div key={item.revision} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs"><span>Revision {item.revision}</span><span className="text-slate-400">{item.scenario?.presetId || 'baseline'}</span></div>)}</div></div>}
  </section>
}

export default function LiveEvaluationPanel({ campaignId }) {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    if (!campaignId) return
    try { setData(await AgentAPI.getCampaignEvaluation(campaignId)); setError('') }
    catch (reason) { setError(reason.message) }
  }, [campaignId])
  useEffect(() => { load() }, [load])

  const runNow = async () => {
    setBusy('run')
    try { await AgentAPI.runCampaignEvaluation(campaignId); await load() }
    catch (reason) { setError(reason.message) }
    finally { setBusy('') }
  }
  const act = async (incident, action) => {
    setBusy(incident.incident_id)
    try { await AgentAPI.actOnEvaluationIncident(campaignId, incident.incident_id, action); await load() }
    catch (reason) { setError(reason.message) }
    finally { setBusy('') }
  }
  const summary = data?.summary || {}
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-3">{[[Activity, 'Health', summary.status || '—'], [AlertTriangle, 'Open incidents', summary.open_count ?? 0], [ShieldCheck, 'Policy', data?.policy?.level || 'L1']].map(([Icon, label, value]) => <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4"><Icon className="h-5 w-5 text-blue-600" /><p className="mt-3 text-xs font-bold uppercase text-slate-400">{label}</p><p className="mt-1 text-xl font-black capitalize text-slate-950">{value}</p></div>)}</div>
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-black text-slate-950">Live Evaluation</h2><p className="mt-1 text-xs text-slate-500">L1 deterministic detection; recovery có approval và verification.</p></div><button type="button" disabled={busy === 'run'} onClick={runNow} className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-xs font-black text-white"><Play className="h-4 w-4" /> Run now</button></div><div className="mt-4 flex items-center gap-2 rounded-xl bg-blue-50 px-3 py-2 text-xs text-blue-800"><BellRing className="h-4 w-4" /> Zalo alert luôn kèm mã INC để không xung đột campaign context.</div>{error && <p className="mt-3 text-xs text-rose-700">{error}</p>}</section>
    <section className="space-y-3">{(data?.incidents || []).map(incident => <article key={incident.incident_id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex justify-between gap-3"><div><div className="flex gap-2"><span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase ${severityTone[incident.severity] || severityTone.low}`}>{incident.severity}</span><span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-black">{incident.state}</span><span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-black text-blue-700">{incident.incident_id}</span></div><h3 className="mt-3 font-black text-slate-950">{incident.title}</h3><p className="mt-1 text-xs text-slate-500">{incident.scope} · revision {incident.dataset_revision}</p></div>{incident.state === 'resolved' && <CheckCircle2 className="h-6 w-6 text-emerald-500" />}</div><pre className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-3 text-[11px] text-slate-200">{JSON.stringify(incident.evidence, null, 2)}</pre><p className="mt-3 text-xs text-slate-600"><strong>Đề xuất:</strong> {incident.recommended_action}</p>{!['resolved', 'dismissed'].includes(incident.state) && <div className="mt-4 flex gap-2"><button disabled={busy === incident.incident_id} onClick={() => act(incident, 'investigate')} className="rounded-lg border px-3 py-2 text-xs font-bold">Investigate</button><button disabled={busy === incident.incident_id} onClick={() => act(incident, 'prepare_recovery')} className="rounded-lg bg-violet-600 px-3 py-2 text-xs font-bold text-white">Prepare recovery</button><button disabled={busy === incident.incident_id} onClick={() => act(incident, 'dismiss')} className="px-3 py-2 text-xs font-bold text-slate-500">Dismiss</button></div>}</article>)}{data && !(data.incidents || []).length && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center"><CheckCircle2 className="mx-auto h-8 w-8 text-emerald-600" /><p className="mt-2 font-black text-emerald-900">Chưa phát hiện incident</p></div>}</section>
  </div>
}
