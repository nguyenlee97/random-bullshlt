import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const review = readFileSync(
  new URL('../src/components/AutopilotReview.jsx', import.meta.url),
  'utf8',
)
const placementReview = review.slice(
  review.indexOf('function PlacementReview'),
  review.indexOf('function PlacementRecoveryReview'),
)

test('Autopilot placement cards contain long zone identifiers at narrow pane widths', () => {
  assert.match(placementReview, /sm:grid-cols-2 2xl:grid-cols-3/)
  assert.match(placementReview, /min-w-0 overflow-hidden rounded-xl/)
  assert.match(placementReview, /min-w-0 flex-1/)
  assert.equal(
    [...placementReview.matchAll(/\[overflow-wrap:anywhere\]/g)].length,
    3,
  )
})
