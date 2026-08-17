import assert from 'node:assert/strict'
import test from 'node:test'

import { getAssignmentIssues, removeInvalidAssignments } from '../src/lib/setupAssignments.js'

const zones = [
  { id: 'zone-ok', name: 'Zone OK' },
  { id: 'zone-stale', name: 'Zone stale' },
  { id: 'zone-review', name: 'Zone review' },
]

test('describes stale and review assignments instead of throwing a generic error', () => {
  const issues = getAssignmentIssues(zones, {
    'zone-ok': 'approved',
    'zone-stale': 'removed-file',
    'zone-review': 'review-file',
  }, [
    { id: 'approved', name: 'approved.png', analysisStatus: 'auto_approved', url: '/approved.png' },
    { id: 'review-file', name: 'review.png', analysisStatus: 'needs_review', url: '/review.png' },
  ])

  assert.deepEqual(issues.map(issue => issue.kind), ['stale_assignment', 'needs_review'])
  assert.match(issues[0].message, /không còn trong workspace/)
  assert.match(issues[1].message, /phê duyệt thủ công/)
})

test('can explicitly remove only invalid zones and preserve valid assignments', () => {
  const data = {
    selectedZoneIds: ['zone-ok', 'zone-stale'],
    assignments: { 'zone-ok': 'approved', 'zone-stale': 'removed-file' },
  }
  const next = removeInvalidAssignments(data, [{ zoneId: 'zone-stale' }])
  assert.deepEqual(next.selectedZoneIds, ['zone-ok'])
  assert.deepEqual(next.assignments, { 'zone-ok': 'approved' })
})
