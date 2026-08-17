import assert from 'node:assert/strict'
import test from 'node:test'

import {
  AUTOPILOT_CHECKPOINT_OBSERVATION,
  classifyAutopilotCheckpointObservation,
} from '../src/demo/autopilotCheckpointSync.js'

const classify = (overrides = {}) => classifyAutopilotCheckpointObservation({
  expectedTaskKeys: ['assign_creatives'],
  taskKey: '',
  status: 'running',
  lastHandledTask: 'analyze_creatives',
  ...overrides,
})

test('keeps waiting while the just-handled creative checkpoint is still exposed', () => {
  assert.equal(
    classify({
      taskKey: 'analyze_creatives',
      status: 'waiting_review',
    }),
    AUTOPILOT_CHECKPOINT_OBSERVATION.STALE_PREVIOUS,
  )
})

test('recognizes the next creative checkpoint once Autopilot advances', () => {
  assert.equal(
    classify({
      taskKey: 'assign_creatives',
      status: 'waiting_review',
    }),
    AUTOPILOT_CHECKPOINT_OBSERVATION.EXPECTED,
  )
})

test('still reports a genuinely different review checkpoint', () => {
  assert.equal(
    classify({
      taskKey: 'rank_placements',
      status: 'waiting_review',
    }),
    AUTOPILOT_CHECKPOINT_OBSERVATION.UNEXPECTED,
  )
})

test('recognizes terminal and in-progress run states', () => {
  assert.equal(
    classify({ status: 'failed' }),
    AUTOPILOT_CHECKPOINT_OBSERVATION.TERMINAL,
  )
  assert.equal(
    classify({ status: 'running' }),
    AUTOPILOT_CHECKPOINT_OBSERVATION.PENDING,
  )
})
