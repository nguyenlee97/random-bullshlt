const APPROVED_STATUSES = new Set(['auto_approved', 'approved_override'])

export function getAssignmentIssues(selectedZones = [], assignments = {}, files = []) {
  const filesById = new Map(files.map(file => [String(file.id || file._id), file]))
  return selectedZones.flatMap(zone => {
    const zoneId = String(zone.id || '')
    const fileId = assignments?.[zoneId]
    const file = fileId == null ? null : filesById.get(String(fileId))
    let kind = ''
    let message = ''

    if (!fileId) {
      kind = 'unassigned'
      message = 'Chưa gắn creative.'
    } else if (!file) {
      kind = 'stale_assignment'
      message = 'Creative đã gắn không còn trong workspace.'
    } else if (!APPROVED_STATUSES.has(file.analysisStatus)) {
      kind = file.analysisStatus === 'needs_review' ? 'needs_review' : 'not_approved'
      message = file.analysisStatus === 'needs_review'
        ? `Creative ${file.name} cần phê duyệt thủ công.`
        : `Creative ${file.name} chưa hoàn tất phân tích.`
    } else if (!file.url) {
      kind = 'missing_url'
      message = `Creative ${file.name} chưa có URL upload.`
    }

    return kind ? [{ zoneId, zoneName: zone.name || zoneId, fileId, kind, message }] : []
  })
}

export function removeInvalidAssignments(data = {}, issues = []) {
  const invalid = new Set(issues.map(issue => String(issue.zoneId)))
  const selectedZoneIds = (data.selectedZoneIds || [])
    .filter(zoneId => !invalid.has(String(zoneId)))
  const keep = new Set(selectedZoneIds.map(String))
  const assignments = Object.fromEntries(
    Object.entries(data.assignments || {}).filter(([zoneId]) => keep.has(String(zoneId))),
  )
  return { ...data, selectedZoneIds, assignments, submitted: false }
}
