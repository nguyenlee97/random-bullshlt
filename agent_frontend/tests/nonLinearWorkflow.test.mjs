import test from 'node:test'
import assert from 'node:assert/strict'

import {
  deriveStepStatuses,
  deriveResumeStep,
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

test('queued creative stays pending until every analysis has a terminal verdict', () => {
  const statuses = Array(7).fill('pending')
  const queued = deriveStepStatuses(statuses, {
    artifacts: {
      creative: {
        status: 'approved',
        value: { files: [{ id: 'f1', name: 'creative.png', analysisStatus: 'queued' }] },
      },
      creative_verdict: { status: 'missing', value: null },
    },
  })
  assert.equal(queued[2], 'pending')

  const replacingPreviousVerdict = deriveStepStatuses(['done', 'done', 'done', ...Array(4).fill('pending')], {
    artifacts: {
      creative: {
        status: 'approved',
        value: { files: [{ id: 'f1', name: 'creative.png', analysisStatus: 'processing' }] },
      },
      creative_verdict: { status: 'stale', value: { files: [] } },
    },
  })
  assert.equal(replacingPreviousVerdict[2], 'pending')

  const complete = deriveStepStatuses(statuses, {
    artifacts: {
      creative: {
        status: 'approved',
        value: { files: [{ id: 'f1', name: 'creative.png', analysisStatus: 'queued' }] },
      },
      creative_verdict: {
        status: 'approved',
        value: { files: [{ name: 'creative.png', status: 'auto_approved' }] },
      },
    },
  })
  assert.equal(complete[2], 'pending')
  const confirmed = deriveStepStatuses(statuses, {
    artifacts: {
      creative: {
        status: 'approved',
        value: { files: [{ id: 'f1', name: 'creative.png', analysisStatus: 'queued' }] },
      },
      creative_verdict: {
        status: 'approved',
        value: { files: [{ name: 'creative.png', status: 'auto_approved' }] },
      },
    },
  }, { creative_review_confirmed: true })
  assert.equal(confirmed[2], 'done')
})

test('Guided resume uses durable order and report progress instead of stale Setup state', () => {
  const pending = Array(7).fill('pending')
  const withOrder = deriveStepStatuses(pending, { artifacts: {} }, { order_created: true })
  assert.equal(withOrder[3], 'done')
  assert.equal(withOrder[4], 'done')
  assert.equal(deriveResumeStep(withOrder, { order_created: true }), 4)
  assert.equal(deriveResumeStep(withOrder, {
    order_created: true,
    report_started: true,
    report_campaign_id: 'ORD-2026-009',
  }), 5)
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
