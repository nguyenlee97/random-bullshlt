import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const panel = readFileSync(new URL('../src/components/AutopilotPanel.jsx', import.meta.url), 'utf8')
const review = readFileSync(new URL('../src/components/AutopilotReview.jsx', import.meta.url), 'utf8')
const creative = readFileSync(new URL('../src/steps/CreativeStep.jsx', import.meta.url), 'utf8')
const crop = readFileSync(new URL('../src/steps/creative/ImageCropModal.jsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')

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
  assert.match(creative, /nearestRatioFile/)
  assert.match(creative, /operator_adapted/)
  assert.match(creative, /<ImageCropModal/)
  assert.match(crop, /Scale toàn ảnh \(có thể méo\)/)
  assert.match(crop, /\^\(data:\|https\?:\|blob:\)/)
})
