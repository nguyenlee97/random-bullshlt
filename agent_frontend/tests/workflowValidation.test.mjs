import test from 'node:test'
import assert from 'node:assert/strict'

import {
  canApproveWorkflowStep,
  isBriefReady,
  responseAllowsAdvance,
} from '../src/lib/workflowValidation.js'

const validBrief = {
  brand: 'Advertising Agent',
  objective: 'awareness',
  kpi: 'Reach',
  budget: 25,
  startDate: '2026-08-01',
  endDate: '2026-08-15',
}

test('an incomplete or reversed-date brief cannot be confirmed', () => {
  assert.equal(isBriefReady(validBrief), true)
  assert.equal(isBriefReady({ ...validBrief, startDate: '' }), false)
  assert.equal(isBriefReady({ ...validBrief, endDate: '2026-07-01' }), false)
  assert.equal(canApproveWorkflowStep(0, { brief: { ...validBrief, kpi: '' } }, []), false)
})

test('a server validation response never advances the workflow', () => {
  assert.equal(responseAllowsAdvance({ metadata: { tool: 'brief_validate' } }), false)
  assert.equal(responseAllowsAdvance({ metadata: { tool: 'creative_blocked' } }), false)
  assert.equal(responseAllowsAdvance({ metadata: { tool: 'brief_handler' } }), true)
  assert.equal(responseAllowsAdvance(null), false)
})
