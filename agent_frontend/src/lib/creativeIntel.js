export const TERMINAL_CREATIVE_STATUSES = new Set([
  'auto_approved',
  'needs_review',
  'approved_override',
])

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
