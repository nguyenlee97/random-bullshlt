const BLOCKING_RESPONSE_TOOLS = new Set([
  'brief_validate',
  'audience_validate',
  'creative_blocked',
  'creative_analysis_error',
])

export function isBriefReady(brief = {}) {
  const start = String(brief.startDate || '')
  const end = String(brief.endDate || '')
  return Boolean(
    String(brief.brand || '').trim()
    && String(brief.objective || '').trim()
    && String(brief.kpi || '').trim()
    && Number(brief.budget) > 0
    && start
    && end
    && end >= start
  )
}

export function canApproveWorkflowStep(stepIndex, formState = {}, stepStatuses = []) {
  if (stepStatuses[stepIndex] === 'done') return false
  switch (stepIndex) {
    case 0: return isBriefReady(formState.brief)
    case 1: return (formState.segment?.attrs || []).length > 0
    case 2: return (formState.creative?.files || []).length > 0
    case 3: return false
    case 5: return Boolean(formState.report?.analyzed)
    case 6: return Boolean(formState.email?.sent)
    default: return true
  }
}

export function responseAllowsAdvance(response) {
  const tool = response?.metadata?.tool
  return Boolean(response) && !BLOCKING_RESPONSE_TOOLS.has(tool)
}
