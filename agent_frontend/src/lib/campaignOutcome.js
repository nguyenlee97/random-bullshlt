const asObject = value => (value && typeof value === 'object' ? value : {})

const artifactValue = (workspace, name) => workspace?.artifacts?.[name]?.value

const taskValue = (taskByKey, key) => {
  const task = taskByKey?.[key]
  return task?.result ?? task?.pending_artifact?.value
}

const firstValue = (...values) => values.find(value => value !== undefined && value !== null)

const creativeId = (file, index) => String(file?.id || file?._id || `autopilot-creative-${index}`)

const normalizeCreative = (file, index) => ({
  ...asObject(file),
  id: creativeId(file, index),
  name: file?.name || file?.formatId || `Creative ${index + 1}`,
  type: file?.type || file?.mimeType || 'image/png',
  dataUrl: file?.dataUrl || file?.url || '',
  url: file?.url || file?.dataUrl || '',
})

const normalizeAssignments = (rawAssignments, files) => Object.fromEntries(
  Object.entries(asObject(rawAssignments)).flatMap(([zoneId, rawFile]) => {
    const index = Number(rawFile)
    if (Number.isInteger(index) && files[index]) return [[zoneId, files[index].id]]
    const existing = files.find(file => file.id === String(rawFile) || file.name === rawFile)
    return existing ? [[zoneId, existing.id]] : []
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

  const files = (creative.files || []).map(normalizeCreative)
  const rawAssignments = assignmentArtifact.assignments || assignmentArtifact
  const assignments = normalizeAssignments(rawAssignments, files)
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
