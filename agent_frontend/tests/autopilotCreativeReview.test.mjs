import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const review = readFileSync(
  new URL('../src/components/AutopilotReview.jsx', import.meta.url),
  'utf8',
)

test('Autopilot creative review renders the full analysis result inline', () => {
  assert.match(review, /export function CreativeAnalysisReview/)
  assert.match(review, /data-testid="autopilot-creative-analysis-results"/)
  assert.match(review, /file\.review_reasons \|\| file\.reviewReasons/)
  assert.match(review, /vlm\.review_notes/)
  assert.match(review, /Kích thước đo được/)
  assert.match(review, /Độ tin cậy VLM/)
})

test('skipped analysis and assignment mapping remain reusable UI artifacts', () => {
  assert.match(review, /value\.analysis_skipped/)
  assert.match(review, /Đã bỏ qua Creative Intelligence/)
  assert.match(review, /export function AssignmentReview/)
  assert.match(review, /Object\.entries\(assignments\)/)
})
