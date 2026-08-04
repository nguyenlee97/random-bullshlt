import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const panel = readFileSync(new URL('../src/components/AutopilotPanel.jsx', import.meta.url), 'utf8')
const review = readFileSync(new URL('../src/components/AutopilotReview.jsx', import.meta.url), 'utf8')
const creative = readFileSync(new URL('../src/steps/CreativeStep.jsx', import.meta.url), 'utf8')
const crop = readFileSync(new URL('../src/steps/creative/ImageCropModal.jsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const workspacePane = readFileSync(new URL('../src/components/WorkspacePane/index.jsx', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const chat = readFileSync(new URL('../src/hooks/useChat.js', import.meta.url), 'utf8')

test('placement mismatch exposes recoverable crop and generation actions', () => {
  assert.match(review, /PlacementRecoveryReview/)
  assert.match(review, /Có thể xử lý ngay mà không phải hủy run/)
  assert.match(panel, /Crop\/scale ảnh hiện có/)
  assert.match(panel, /generateAutopilotCreativeRecovery/)
  assert.match(panel, /data-demo="autopilot-review-dock"/)
  assert.match(panel, /border-t border-amber-200/)
  assert.doesNotMatch(panel, /backdrop-blur-md sm:flex-row sm:items-center/)
  assert.match(api, /creative-recovery\/generate/)
  assert.match(api, /AbortSignal\.timeout\(240000\)/)
})

test('creative editor can derive an exact planned format from an uploaded image', () => {
  assert.match(creative, /data-demo="creative-format-recovery"/)
  assert.match(creative, /selectRepairSourceFile/)
  assert.match(creative, /operator_adapted/)
  assert.match(creative, /<ImageCropModal/)
  assert.match(crop, /Scale toàn ảnh/)
  assert.match(crop, /hidden sm:inline.*\(có thể méo\)/)
  assert.match(crop, /onPointerDown/)
  assert.match(crop, /sm:flex-row/)
  assert.match(crop, /creativeImageSource\(src\)/)
  assert.match(crop, /crossOrigin=\{creativeImageCrossOrigin\(dataUrl\)\}/)
})

test('crop interaction coalesces pointer updates and exports PNG asynchronously', () => {
  assert.match(crop, /window\.requestAnimationFrame/)
  assert.match(crop, /window\.cancelAnimationFrame/)
  assert.match(crop, /canvas\.toBlob/)
  assert.match(crop, /const img = imgRef\.current/)
  assert.doesNotMatch(crop, /toDataURL\('image\/png'\)/)
  assert.doesNotMatch(crop, /\[box, display, clampBox/)
  assert.match(crop, /disabled=\{!box \|\| processing\}/)
})

test('crop or scale persists and completes the Autopilot recovery transaction', () => {
  assert.match(creative, /await onRepairSave\(nextCreative\)/)
  assert.match(creative, /Đang tải, phân tích và lưu creative vào workspace/)
  assert.match(workspacePane, /onRepairSave=\{autopilotMode \? saveAutopilotEditor/)
  assert.match(app, /completeReadyCreative:\s*editingStep === 2 && hasCreativeOverride/)
  assert.match(
    chat,
    /if \(completeReadyCreative\) \{[\s\S]*?AgentAPI\.approveCreative\([\s\S]*?files:\s*prepared[\s\S]*?responseAllowsAdvance\(response\)/,
  )
})

test('Autopilot footer save never treats the React click event as creative data', () => {
  assert.match(workspacePane, /onClick=\{\(\) => saveAutopilotEditor\(\)\}/)
  assert.match(app, /const hasCreativeOverride = Boolean\([\s\S]*?Array\.isArray\(creativeOverride\.files\)/)
  assert.match(app, /creative:\s*hasCreativeOverride \? creativeOverride : formState\.creative/)
})
