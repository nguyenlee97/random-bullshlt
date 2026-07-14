import test from 'node:test'
import assert from 'node:assert/strict'

import {
  deriveStepStatuses,
  firstRecomputeStep,
  isStepReachable,
  workspacePatchTarget,
} from '../src/lib/nonLinearWorkflow.js'

test('input workspaces are reachable out of order', () => {
  const statuses = Array(7).fill('pending')
  assert.equal(isStepReachable(0, 0, statuses), true)
  assert.equal(isStepReachable(2, 0, statuses), true)
  assert.equal(isStepReachable(3, 0, statuses), true)
  assert.equal(isStepReachable(4, 0, statuses), false)
})

test('canonical stale artifacts mark only mapped workflow steps stale', () => {
  const statuses = ['done', 'done', 'done', 'done', 'pending', 'pending', 'pending']
  const next = deriveStepStatuses(statuses, {
    artifacts: {
      brief: { status: 'approved', value: { brand: 'A' } },
      audience: { status: 'approved', value: { attrs: [] } },
      targeting: { status: 'stale', value: { age: ['25-34'] } },
      creative: { status: 'approved', value: { files: [] } },
      placements: { status: 'approved', value: { selectedZoneIds: [] } },
    },
  })
  assert.deepEqual(next, ['done', 'stale', 'done', 'done', 'pending', 'pending', 'pending'])
})

test('typed proposal fields map to the correct browser state and step', () => {
  assert.deepEqual(workspacePatchTarget('targeting'), { path: 'segment.targeting', step: 1 })
  assert.deepEqual(workspacePatchTarget('creative.files'), { path: 'creative.files', step: 2 })
  assert.deepEqual(workspacePatchTarget('setup.selectedZoneIds'), { path: 'setup.selectedZoneIds', step: 3 })
  assert.deepEqual(workspacePatchTarget('assignments'), { path: 'setup.assignments', step: 3 })
})

test('plan diff links to the earliest affected workspace step', () => {
  assert.equal(firstRecomputeStep({ recompute_order: ['creative_verdict', 'assignments'] }), 2)
  assert.equal(firstRecomputeStep({ recompute_order: [] }), null)
})
