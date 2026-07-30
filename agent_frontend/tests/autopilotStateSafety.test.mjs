import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const panel = readFileSync(
  new URL('../src/components/AutopilotPanel.jsx', import.meta.url),
  'utf8',
)
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')

test('review jump scrolls inside the mounted Autopilot canvas without mutating the route', () => {
  assert.match(panel, /const scrollToReviewArtifact = event =>/)
  assert.match(panel, /event\?\.preventDefault\?\.\(\)/)
  assert.match(panel, /target\.scrollIntoView\(\{ behavior: 'smooth', block: 'start' \}\)/)
  assert.doesNotMatch(panel, /href="#autopilot-review-artifact"/)
  assert.match(panel, /onClick=\{scrollToReviewArtifact\}/)
})

test('creative source stays locked until the canonical brief is confirmed', () => {
  assert.match(panel, /disabled=\{!briefReady \|\| loading\}/)
  assert.match(panel, /Nguồn creative đang khóa cho đến khi Brief được xác nhận/)
  assert.match(panel, /if \(loading \|\| !briefReady\)/)
})

test('uploaded creative disables fully automatic policy with an accessible tooltip', () => {
  assert.match(panel, /item\.value === 'auto_build_draft' && creativeSource === 'upload'/)
  assert.match(panel, /const policyDisabled = policyLocked \|\| uploadBlocksAutomatic \|\| loading/)
  assert.match(panel, /aria-disabled=\{policyDisabled\}/)
  assert.match(panel, /role="tooltip"/)
  assert.match(panel, /group-hover:block group-focus-within:block/)
  assert.match(panel, /value === 'upload' && policy === 'auto_build_draft'/)
})

test('durable Autopilot milestones are injected once and hydrate report state', () => {
  assert.match(app, /autopilotMilestonesShownRef/)
  assert.match(app, /metadata\.campaign_id \|\| autopilotSummary\?\.reportCampaignId/)
  assert.match(app, /\['report_generating', 'report_ready'\]\.includes\(metadata\.kind\)/)
  assert.match(app, /tool: 'autopilot_milestone'/)
})
