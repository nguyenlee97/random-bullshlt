export const TERMINAL_CREATIVE_STATUSES = new Set([
  'auto_approved',
  'needs_review',
  'approved_override',
])

export const APPROVED_CREATIVE_STATUSES = new Set([
  'auto_approved',
  'approved_override',
])

export function creativeReviewState(files = []) {
  if (!files.length) return 'empty'
  const statuses = files.map(file => file.analysisStatus || '')
  if (statuses.some(status => status === 'needs_review')) return 'blocked'
  if (statuses.every(status => APPROVED_CREATIVE_STATUSES.has(status))) return 'ready'
  return 'analysis_required'
}

export function isRetryableCreativeAnalysisFailure(file = {}) {
  if (file.analysisStatus !== 'needs_review') return false
  if (file.vlmError) return true
  return (file.reviewReasons || []).some(reason => (
    String(reason).trim().toLocaleLowerCase('vi').startsWith('phân tích hình ảnh gặp lỗi')
  ))
}

const terminalStatus = verdict => (
  TERMINAL_CREATIVE_STATUSES.has(verdict?.effective_status)
    ? verdict.effective_status
    : verdict?.status
)

const sameCreative = (file, verdict) => (
  verdict?.analysis_id === file?.analysisId
  || (verdict?.url && verdict.url === file?.url)
  || (verdict?.name && verdict.name === file?.name)
)

export function mergeCreativeVerdicts(creative = {}, verdictArtifact = {}) {
  const verdicts = verdictArtifact?.files || []
  if (!Array.isArray(creative?.files) || !verdicts.length) return creative

  return {
    ...creative,
    files: creative.files.map(file => {
      const verdict = verdicts.find(item => sameCreative(file, item))
      if (!verdict) return file
      const deterministic = verdict.deterministic || file.deterministic || {}
      return {
        ...file,
        analysisId: verdict.analysis_id || file.analysisId,
        analysisStatus: terminalStatus(verdict) || file.analysisStatus,
        reviewReasons: verdict.review_reasons || file.reviewReasons || [],
        deterministic,
        vlm: verdict.vlm || file.vlm || {},
        vlmError: verdict.vlm_error || file.vlmError || null,
        vlmProvider: verdict.vlm_provider || file.vlmProvider || '',
        vlmModel: verdict.vlm_model || file.vlmModel || '',
        vlmRouteKey: verdict.vlm_route_key || file.vlmRouteKey || '',
        override: verdict.override || file.override || {},
        width: deterministic.width || file.width,
        height: deterministic.height || file.height,
      }
    }),
  }
}

export function defaultPlacementSelection(value = {}, limit = 6) {
  const ids = value.candidate_zone_ids
    || (value.candidates || value.zones || []).map(zone => zone.id).filter(Boolean)
  return ids.slice(0, Math.max(1, limit))
}
