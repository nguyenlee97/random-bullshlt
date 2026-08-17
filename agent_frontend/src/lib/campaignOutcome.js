const asObject = value => (value && typeof value === 'object' ? value : {})

const artifactValue = (workspace, name) => workspace?.artifacts?.[name]?.value

const taskValue = (taskByKey, key) => {
  const task = taskByKey?.[key]
  return task?.result ?? task?.pending_artifact?.value
}

const firstValue = (...values) => values.find(value => value !== undefined && value !== null)

export function placementIdsFromValue(value) {
  const candidate = asObject(value)
  const sources = [
    candidate.selectedZoneIds,
    candidate.zoneIds,
    candidate.placements,
    candidate.summary?.placements,
    candidate.payload?.placements,
    candidate.order?.placements,
    candidate.order?.order?.placements,
  ]
  const list = sources.find(Array.isArray)
  if (list) return list.filter(Boolean)
  const mapping = sources.find(item => item && typeof item === 'object')
  return mapping ? Object.keys(mapping) : []
}

export function campaignWarningText(warning) {
  if (typeof warning === 'string') return warning
  if (!warning || typeof warning !== 'object') return String(warning || '')
  const message = String(warning.message || warning.reason || warning.code || 'Cảnh báo campaign')
  const zoneId = warning.zoneId || warning.zone_id || warning.placementId
  return zoneId ? `${zoneId}: ${message}` : message
}

export function creativePlacementCoverage(files = [], assignmentValue = {}) {
  const assignments = asObject(assignmentValue.assignments || assignmentValue)
  return files.map((file, index) => {
    const assigned = Object.entries(assignments)
      .filter(([, fileRef]) => Number(fileRef) === index || String(fileRef) === String(file?.id || ''))
      .map(([zoneId]) => zoneId)
    return [...new Set([...(file?.intendedZoneIds || []), ...assigned])]
  })
}

const creativeId = (file, index) => String(file?.id || file?._id || `autopilot-creative-${index}`)

const normalizeCreative = (file, index) => ({
  ...asObject(file),
  id: creativeId(file, index),
  name: file?.name || file?.formatId || `Creative ${index + 1}`,
  type: file?.type || file?.mimeType || 'image/png',
  dataUrl: file?.dataUrl || file?.url || '',
  url: file?.url || file?.dataUrl || '',
})

export const normalizeCreativeFiles = (files = []) => files.map(normalizeCreative)

export const normalizeAssignmentsForEditor = (rawAssignments, files = []) => {
  const candidate = asObject(rawAssignments)
  const assignments = asObject(candidate.assignments || candidate)
  return Object.fromEntries(
    Object.entries(assignments).flatMap(([zoneId, rawFile]) => {
    const index = Number(rawFile)
    if (Number.isInteger(index) && files[index]) return [[zoneId, files[index].id]]
    const existing = files.find(file => file.id === String(rawFile) || file.name === rawFile)
    return existing ? [[zoneId, existing.id]] : []
    }),
  )
}

export const assignmentsToFileIndexes = (rawAssignments, files = []) => Object.fromEntries(
  Object.entries(asObject(rawAssignments)).flatMap(([zoneId, rawFile]) => {
    const fileIndex = files.findIndex((file, index) => (
      String(file?.id || file?._id || `autopilot-creative-${index}`) === String(rawFile)
      || file?.name === rawFile
    ))
    return fileIndex >= 0 ? [[zoneId, fileIndex]] : []
  }),
)

const unwrapOrder = value => {
  const candidate = asObject(value)
  return asObject(candidate.order && typeof candidate.order === 'object' ? candidate.order : candidate)
}

export function buildCampaignOutcome({ workspace, taskByKey = {}, fallbackBrief = {} } = {}) {
  const brief = asObject(firstValue(
    artifactValue(workspace, 'brief'),
    taskValue(taskByKey, 'normalize_brief'),
    fallbackBrief,
  ))
  const strategy = asObject(firstValue(
    taskValue(taskByKey, 'generate_strategy'),
    artifactValue(workspace, 'strategy'),
  ))
  const audience = asObject(firstValue(
    taskValue(taskByKey, 'retrieve_audience'),
    artifactValue(workspace, 'audience'),
  ))
  const targeting = asObject(firstValue(
    taskValue(taskByKey, 'derive_targeting'),
    artifactValue(workspace, 'targeting'),
  ))
  const placements = asObject(firstValue(
    taskValue(taskByKey, 'rank_placements'),
    artifactValue(workspace, 'placements'),
  ))
  const creative = asObject(firstValue(
    taskValue(taskByKey, 'prepare_creatives'),
    artifactValue(workspace, 'creative'),
  ))
  const assignmentArtifact = asObject(firstValue(
    taskValue(taskByKey, 'assign_creatives'),
    artifactValue(workspace, 'assignments'),
  ))
  const forecast = asObject(firstValue(
    taskValue(taskByKey, 'forecast'),
    artifactValue(workspace, 'forecast'),
  ))
  const order = unwrapOrder(firstValue(
    taskValue(taskByKey, 'verify_order'),
    taskValue(taskByKey, 'create_order'),
    artifactValue(workspace, 'order'),
  ))
  const report = asObject(firstValue(
    taskValue(taskByKey, 'create_setup_report'),
    artifactValue(workspace, 'report'),
  ))
  const guard = asObject(firstValue(
    taskValue(taskByKey, 'run_order_guard'),
    artifactValue(workspace, 'order_guard'),
  ))

  const files = normalizeCreativeFiles(creative.files || [])
  const rawAssignments = assignmentArtifact.assignments || assignmentArtifact
  const assignments = normalizeAssignmentsForEditor(rawAssignments, files)
  const zones = placements.zones || []
  const selectedZoneIds = placements.selectedZoneIds || zones.map(zone => zone.id).filter(Boolean)

  return {
    brief,
    strategy,
    audience,
    targeting,
    placements,
    creative: { ...creative, files },
    assignments: { ...assignmentArtifact, assignments },
    forecast,
    order,
    report,
    guard,
    selectedZoneIds,
    zones,
    setup: { assignments, creativeFiles: files },
    audienceSize: Number(audience.size || audience.estimated_size || forecast.estimated_reach || 0),
    orderId: order.id || order._id || order.orderId || '',
    orderStatus: order.status || 'unknown',
    performanceAvailable: report.performance_data_available === true,
  }
}

export function campaignDeliveryState(outcome) {
  const status = outcome?.orderStatus
  if (!outcome?.orderId) return { tone: 'neutral', label: 'Chưa tạo order', live: false }
  if (status === 'active') return { tone: 'success', label: 'Đang hoạt động', live: true }
  if (status === 'pending') return { tone: 'warning', label: 'Chờ kích hoạt', live: false }
  if (['cancelled', 'rejected', 'failed'].includes(status)) {
    return { tone: 'danger', label: 'Không hoạt động', live: false }
  }
  return { tone: 'neutral', label: status || 'Không xác định', live: false }
}

const seededNumber = text => [...String(text || 'campaign')].reduce(
  (hash, char) => ((hash * 31) + char.charCodeAt(0)) >>> 0, 2166136261,
)

const dateRange = (startValue, endValue) => {
  const start = new Date(`${startValue || ''}T00:00:00`)
  const end = new Date(`${endValue || ''}T00:00:00`)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return []
  const count = Math.min(Math.floor((end - start) / 86400000) + 1, 14)
  return Array.from({ length: count }, (_, index) => {
    const value = new Date(start)
    value.setDate(start.getDate() + index)
    return value.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })
  })
}

/** Deterministic showcase data derived from one active campaign's real setup. */
export function buildSyntheticPerformance(outcome) {
  if (!outcome?.orderId || outcome.orderStatus !== 'active') return null
  const labels = dateRange(outcome.brief.startDate, outcome.brief.endDate)
  if (!labels.length) labels.push('Ngày 1', 'Ngày 2', 'Ngày 3')
  const seed = seededNumber(`${outcome.orderId}:${outcome.brief.brand}`)
  const weights = labels.map((_, index) => 0.82 + ((seed + index * 37) % 37) / 100)
  const totalWeight = weights.reduce((sum, value) => sum + value, 0)
  const totalImpressions = Math.max(Number(outcome.forecast.estimated_impressions || 0), 0)
  const totalReach = Math.max(Number(outcome.forecast.estimated_reach || 0), 0)
  const totalSpend = Math.max(Number(outcome.forecast.budget_vnd || Number(outcome.brief.budget || 0) * 1_000_000), 0)
  const baseCtr = {
    awareness: 0.85, consideration: 1.15, conversion: 1.55, retention: 1.05,
  }[outcome.brief.objective] || 1
  const selected = outcome.strategy.selected || outcome.strategy.recommended
  const ctr = Math.round((baseCtr + (selected === 'quality_first' ? 0.18 : selected === 'reach_first' ? -0.08 : 0)) * 100) / 100
  const rows = labels.map((label, index) => {
    const share = weights[index] / totalWeight
    const impressions = Math.round(totalImpressions * share)
    return {
      label,
      impressions,
      reach: Math.round(totalReach * share),
      clicks: Math.round(impressions * ctr / 100),
      spend: Math.round(totalSpend * share),
    }
  })
  const clicks = rows.reduce((sum, row) => sum + row.clicks, 0)
  const placements = (outcome.zones || []).map(zone => ({
    id: zone.id,
    name: zone.name || zone.id,
    channel: zone.channel || zone.platform || 'Placement',
    cpm: Number(zone.cpm || outcome.forecast.average_cpm || 0),
    reach: Number(zone.reach || 0),
  })).sort((left, right) => right.reach - left.reach)

  return {
    mode: 'synthetic_showcase',
    labels,
    rows,
    placements,
    metrics: {
      impressions: totalImpressions,
      reach: totalReach,
      clicks,
      ctr,
      spend: totalSpend,
      averageCpm: Number(outcome.forecast.average_cpm || 0),
    },
  }
}
