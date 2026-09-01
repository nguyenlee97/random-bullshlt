// Analytics hosts the tool; the Agent-origin frame owns authentication and mutations.
export function scenarioFrameUrl(agentBase, campaignId) {
  const url = new URL('/evaluation/scenarios', agentBase)
  url.searchParams.set('campaignId', campaignId)
  return url
}

export function isScenarioEvent(event, frame, origin, campaignId) {
  return event.source === frame.contentWindow && event.origin === origin &&
    event.data?.campaignId === campaignId &&
    (event.data.type === 'scenario-applied' || event.data.type === 'scenario-busy')
}

export function installScenarioLab({ select, onApplied }) {
  const trigger = document.getElementById('btnScenarioLab')
  const dialog = document.getElementById('scenarioDialog')
  const frame = document.getElementById('scenarioFrame')
  const close = document.getElementById('scenarioClose')
  const status = document.getElementById('scenarioStatus')
  const local = ['localhost', '127.0.0.1'].includes(location.hostname)
  const agentBase = window.__ADSTACK_CONFIG__?.agentUiBase || (local ? 'http://localhost:5175/' : 'https://agent.pawgrammers.io.vn/')
  let campaignId = '', frameOrigin = '', busy = false
  const update = () => { trigger.disabled = !select.value; trigger.title = select.value ? 'Giả lập dữ liệu cho campaign đã chọn' : 'Chọn một campaign cụ thể trước' }
  select.addEventListener('change', update)
  trigger.addEventListener('click', () => {
    if (!select.value) return
    const url = scenarioFrameUrl(agentBase, select.value)
    if (campaignId !== select.value || !frame.src) frame.src = url.href
    campaignId = select.value; frameOrigin = url.origin
    dialog.showModal()
  })
  close.addEventListener('click', () => { if (!busy) dialog.close() })
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault() })
  dialog.addEventListener('close', () => trigger.focus())
  window.addEventListener('message', async event => {
    if (!isScenarioEvent(event, frame, frameOrigin, campaignId)) return
    if (event.data.type === 'scenario-busy') { busy = event.data.busy === true; close.disabled = busy; return }
    if (!Number.isInteger(event.data.revision) || event.data.revision < 1) return
    status.textContent = 'Đã áp dụng revision ' + event.data.revision + ' — đang tải lại biểu đồ.'
    try { await onApplied(campaignId); status.textContent = 'Biểu đồ đã tải lại từ dữ liệu report.' }
    catch { status.textContent = 'Dữ liệu đã lưu nhưng chưa tải lại được biểu đồ. Hãy tải lại trang.' }
  })
  update()
  return update
}
