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

export function deriveStepStatuses(currentStatuses, workspace) {
  const artifacts = workspace?.artifacts || {}
  return currentStatuses.map((current, index) => {
    const tracked = STEP_ARTIFACTS[index] || []
    if (tracked.some(name => artifacts[name]?.status === 'stale')) return 'stale'

    const primary = PRIMARY_ARTIFACT[index]
    const primaryState = primary ? artifacts[primary] : null
    if (index <= 2 && primaryState?.status === 'approved' && primaryState?.value != null) {
      return 'done'
    }
    if (index === 4 && artifacts.order?.status === 'approved') return 'done'
    if (index === 5 && artifacts.report?.status === 'approved') return 'done'
    return current
  })
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
