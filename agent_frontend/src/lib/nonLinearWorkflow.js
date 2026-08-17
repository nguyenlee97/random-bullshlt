import {
  mergeCreativeVerdicts,
  TERMINAL_CREATIVE_STATUSES,
} from './creativeIntel.js'

export const STEP_ARTIFACTS = [
  ['brief'],
  ['audience', 'targeting'],
  ['creative', 'creative_verdict'],
  ['placements', 'assignments', 'forecast', 'order_draft'],
  ['order'],
  ['report'],
  [],
]

const PRIMARY_ARTIFACT = ['brief', 'audience', 'creative', 'order', 'order', 'report', null]

function creativeAnalysisComplete(artifacts) {
  const creative = artifacts.creative?.value || {}
  const files = Array.isArray(creative.files) ? creative.files : []
  if (!files.length) return null

  const hydrated = mergeCreativeVerdicts(
    creative,
    artifacts.creative_verdict?.value || {},
  )
  const statuses = (hydrated.files || []).map(file => file.analysisStatus).filter(Boolean)

  // Creative records created before Creative Intelligence have no analysis
  // status at all. Keep those historical workspaces resumable. New writes
  // always carry queued/terminal status, so queued work cannot use this path.
  if (!statuses.length) return true
  return statuses.length === files.length
    && statuses.every(status => TERMINAL_CREATIVE_STATUSES.has(status))
}

export function deriveStepStatuses(currentStatuses, workspace, workflowProgress = {}) {
  const artifacts = workspace?.artifacts || {}
  return currentStatuses.map((current, index) => {
    const tracked = STEP_ARTIFACTS[index] || []
    if (
      index === 2
      && artifacts.creative?.status === 'approved'
      && creativeAnalysisComplete(artifacts) === false
    ) {
      // A newly committed Creative revision intentionally makes the previous
      // verdict stale. During that replacement analysis the operator should
      // see active progress, not the stale read-only completed view.
      return 'pending'
    }
    if (tracked.some(name => artifacts[name]?.status === 'stale')) return 'stale'

    const primary = PRIMARY_ARTIFACT[index]
    const primaryState = primary ? artifacts[primary] : null
    if (index <= 1 && primaryState?.status === 'approved' && primaryState?.value != null) {
      return 'done'
    }
    if (index === 2 && primaryState?.status === 'approved' && primaryState?.value != null) {
      const analysisComplete = creativeAnalysisComplete(artifacts)
      if (analysisComplete == null) return current
      if (!analysisComplete) return 'pending'
      // Legacy creative snapshots without analysis statuses remain resumable.
      // New terminal verdicts stay visible until the operator explicitly
      // confirms that they have reviewed the result.
      const files = primaryState.value?.files || []
      const hasAnalysisStatuses = files.some(file => file.analysisStatus)
        || Boolean(artifacts.creative_verdict?.value)
      if (!hasAnalysisStatuses) return 'done'
      return workflowProgress.creative_review_confirmed ? 'done' : current
    }
    const hasOrder = workflowProgress.order_created || artifacts.order?.status === 'approved'
    if (index === 3 && hasOrder) return 'done'
    if (index === 4 && hasOrder) return 'done'
    if (index === 5 && artifacts.report?.status === 'approved') return 'done'
    return current
  })
}

export function deriveResumeStep(stepStatuses, workflowProgress = {}) {
  // Report generation is the terminal Guided destination. Restoring it must
  // not re-trigger generation or fall back to the older Setup compatibility
  // artifact merely because no browser-local step index survived.
  if (workflowProgress.report_started) return 5
  if (workflowProgress.order_created) return 4
  const firstIncomplete = stepStatuses.findIndex(status => status !== 'done')
  return firstIncomplete < 0 ? stepStatuses.length - 1 : firstIncomplete
}

export function isStepReachable(index, currentStep, stepStatuses) {
  if (index <= 3) return true
  if (index === currentStep) return true
  if (['done', 'stale'].includes(stepStatuses[index])) return true
  return stepStatuses.slice(0, index).every(status => status === 'done')
}

export function workspacePatchTarget(field) {
  if (field === 'targeting') return { path: 'segment.targeting', step: 1 }
  if (field === 'assignments') return { path: 'setup.assignments', step: 3 }
  if (field === 'setup.selectedZoneIds') return { path: field, step: 3 }
  if (field === 'creative.files') return { path: field, step: 2 }
  if (field === 'segment' || field === 'audience') return { path: 'segment', step: 1 }
  if (field === 'creative') return { path: 'creative', step: 2 }
  if (field === 'setup' || field === 'placements') return { path: 'setup', step: 3 }
  if (field === 'brief' || field.startsWith('brief.')) return { path: field, step: 0 }
  return { path: field, step: null }
}

export function firstRecomputeStep(plan) {
  const artifact = plan?.recompute_order?.[0]
  if (!artifact) return null
  return STEP_ARTIFACTS.findIndex(items => items.includes(artifact))
}
