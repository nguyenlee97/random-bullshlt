import assert from 'node:assert/strict'
import test from 'node:test'

import {
  MAX_CONCURRENT_GENERATIONS,
  MAX_PENDING_GENERATIONS,
  canEnqueueGeneration,
  countActiveGenerations,
  countPendingGenerations,
  nextQueuedGenerations,
} from '../src/steps/creative/generationQueue.js'

const job = (id, status) => ({ job_id: id, status })

test('generation queue runs two requests and keeps three waiting', () => {
  const jobs = [
    job('active-1', 'generating'),
    job('active-2', 'reserved'),
    job('queued-1', 'queued'),
    job('queued-2', 'queued'),
    job('queued-3', 'queued'),
  ]

  assert.equal(MAX_CONCURRENT_GENERATIONS, 2)
  assert.equal(MAX_PENDING_GENERATIONS, 5)
  assert.equal(countActiveGenerations(jobs), 2)
  assert.equal(countPendingGenerations(jobs), 5)
  assert.equal(canEnqueueGeneration(jobs), false)
  assert.deepEqual(nextQueuedGenerations(jobs), [])
})

test('the oldest queued request starts when an active slot opens', () => {
  const jobs = [
    job('finished', 'succeeded'),
    job('active', 'generating'),
    job('queued-1', 'queued'),
    job('queued-2', 'queued'),
  ]

  assert.equal(countPendingGenerations(jobs), 3)
  assert.equal(canEnqueueGeneration(jobs), true)
  assert.deepEqual(nextQueuedGenerations(jobs).map(item => item.job_id), ['queued-1'])
})

test('completed and failed images do not consume queue capacity', () => {
  const jobs = [
    job('finished', 'succeeded'),
    job('failed', 'failed'),
    job('ambiguous', 'ambiguous'),
    job('queued-1', 'queued'),
    job('queued-2', 'queued'),
  ]

  assert.equal(countActiveGenerations(jobs), 0)
  assert.equal(countPendingGenerations(jobs), 2)
  assert.deepEqual(nextQueuedGenerations(jobs).map(item => item.job_id), ['queued-1', 'queued-2'])
})
