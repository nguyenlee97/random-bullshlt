import { ScenarioLab } from './CampaignEvaluationWorkspace'

export default function ScenarioLabPage() {
  const params = new URLSearchParams(location.search)
  const campaignId = params.get('campaignId') || ''
  const allowed = new Set([location.origin, new URL(import.meta.env.VITE_ANALYTICS_URL || 'https://analytics.pawgrammers.io.vn').origin])
  if (['localhost', '127.0.0.1'].includes(location.hostname)) {
    allowed.add('http://localhost:5174'); allowed.add('http://127.0.0.1:5174')
  }
  let parentOrigin = ''
  try { parentOrigin = new URL(document.referrer).origin } catch {}
  const framed = window.parent !== window
  if (!campaignId || (framed && !allowed.has(parentOrigin))) {
    return <p role="alert" className="p-6">Hãy mở Scenario Lab từ site Analytics được cấu hình và chọn một campaign.</p>
  }
  const notify = data => { if (framed) window.parent.postMessage({ ...data, campaignId }, parentOrigin) }
  return <main className="h-dvh overflow-y-auto bg-white"><ScenarioLab key={campaignId} campaignId={campaignId}
    onBusy={busy => notify({ type: 'scenario-busy', busy })}
    onApplied={result => notify({ type: 'scenario-applied', revision: result.scenario.revision })} /></main>
}
