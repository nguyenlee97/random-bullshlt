import assert from 'node:assert/strict'
import test from 'node:test'
import {
  campaignPageSize, isCompletedCampaign, isLiveCampaign, isOperationalCampaign,
} from '../src/lib/campaignHomeLayout.js'

test('desktop campaign groups use the requested page sizes', () => {
  assert.equal(campaignPageSize('attention'), 4)
  assert.equal(campaignPageSize('completed'), 4)
  assert.equal(campaignPageSize('drafts'), 6)
  assert.equal(campaignPageSize('live'), 2)
  assert.equal(campaignPageSize('archive'), 4)
})

test('compact campaign groups stay at one card per page', () => {
  for (const group of ['attention', 'completed', 'drafts', 'live', 'archive']) {
    assert.equal(campaignPageSize(group, true), 1)
  }
})

test('completed campaigns are operational but excluded from the live group', () => {
  const completed = { phase: 'operational', lifecycle: 'completed' }
  const active = { phase: 'operational', lifecycle: 'active' }
  assert.equal(isOperationalCampaign(completed), true)
  assert.equal(isCompletedCampaign(completed), true)
  assert.equal(isLiveCampaign(completed), false)
  assert.equal(isCompletedCampaign(active), false)
  assert.equal(isLiveCampaign(active), true)
})

test('scheduled and failed orders are not counted as currently live', () => {
  assert.equal(isLiveCampaign({ phase: 'operational', lifecycle: 'scheduled' }), false)
  assert.equal(isLiveCampaign({ phase: 'operational', lifecycle: 'failed' }), false)
  assert.equal(isLiveCampaign({ phase: 'operational', lifecycle: 'active' }), true)
})
