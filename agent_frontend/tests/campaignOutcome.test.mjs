import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildCampaignOutcome, buildSyntheticPerformance, campaignDeliveryState,
  campaignWarningText, creativePlacementCoverage, placementIdsFromValue,
} from '../src/lib/campaignOutcome.js'

test('reads placement IDs from review-stage artifact shapes', () => {
  assert.deepEqual(placementIdsFromValue({ summary: { placements: ['zone-1', 'zone-2'] } }), ['zone-1', 'zone-2'])
  assert.deepEqual(placementIdsFromValue({ payload: { placements: ['zone-3'] } }), ['zone-3'])
  assert.deepEqual(placementIdsFromValue({ selectedZoneIds: ['zone-4'] }), ['zone-4'])
})

test('renders structured assignment warnings as text', () => {
  assert.equal(
    campaignWarningText({ zoneId: 'ZingNews_Masthead', message: 'Tỷ lệ hơi lệch (11%)' }),
    'ZingNews_Masthead: Tỷ lệ hơi lệch (11%)',
  )
})

test('derives uploaded creative coverage from the final assignment artifact', () => {
  assert.deepEqual(
    creativePlacementCoverage(
      [{ id: 'file-a' }, { id: 'file-b', intendedZoneIds: ['zone-existing'] }],
      { assignments: { 'zone-1': 0, 'zone-2': 1 } },
    ),
    [['zone-1'], ['zone-existing', 'zone-2']],
  )
})

test('normalizes Autopilot artifacts for the shared Result surface', () => {
  const outcome = buildCampaignOutcome({
    workspace: {
      artifacts: {
        brief: { value: { brand: 'Mixifood', budget: 5, objective: 'conversion' } },
        audience: { value: { attrs: [{ _id: 'aud-1', fullLabel: 'Người yêu ẩm thực' }] } },
        placements: { value: { selectedZoneIds: ['zone-1'], zones: [{ id: 'zone-1', name: 'Top banner' }] } },
        creative: { value: { files: [{ name: 'banner.png', url: 'http://localhost/banner.png' }] } },
        assignments: { value: { assignments: { 'zone-1': 0 } } },
        forecast: { value: { estimated_reach: 36101, estimated_impressions: 108303 } },
        order: { value: { order: { id: 'ORD-1', status: 'pending' }, verified: true } },
        report: { value: { kind: 'setup_report', performance_data_available: false } },
      },
    },
  })

  assert.equal(outcome.orderId, 'ORD-1')
  assert.equal(outcome.orderStatus, 'pending')
  assert.equal(outcome.audienceSize, 36101)
  assert.equal(outcome.creative.files[0].dataUrl, 'http://localhost/banner.png')
  assert.equal(outcome.setup.assignments['zone-1'], outcome.creative.files[0].id)
  assert.deepEqual(outcome.selectedZoneIds, ['zone-1'])
  assert.equal(outcome.performanceAvailable, false)
})

test('prefers current task results over an older workspace snapshot', () => {
  const outcome = buildCampaignOutcome({
    workspace: { artifacts: { forecast: { value: { estimated_reach: 10 } } } },
    taskByKey: {
      forecast: { result: { estimated_reach: 25 } },
      verify_order: { result: { order: { _id: 'ORD-2', status: 'active' } } },
    },
  })

  assert.equal(outcome.forecast.estimated_reach, 25)
  assert.equal(outcome.orderId, 'ORD-2')
  assert.deepEqual(campaignDeliveryState(outcome), {
    tone: 'success', label: 'Đang hoạt động', live: true,
  })
})

test('never treats a date-range-only pending order as live', () => {
  const outcome = buildCampaignOutcome({
    fallbackBrief: { startDate: '2026-01-01', endDate: '2099-12-31' },
    taskByKey: { create_order: { result: { order: { id: 'ORD-3', status: 'pending' } } } },
  })

  assert.equal(campaignDeliveryState(outcome).live, false)
  assert.equal(campaignDeliveryState(outcome).label, 'Chờ kích hoạt')
})

test('builds deterministic synthetic reporting only for active campaigns', () => {
  const active = buildCampaignOutcome({
    fallbackBrief: {
      brand: 'Mixifood', objective: 'conversion', budget: 5,
      startDate: '2026-07-16', endDate: '2026-07-18',
    },
    taskByKey: {
      generate_strategy: { result: { selected: 'quality_first' } },
      forecast: { result: { estimated_reach: 30_000, estimated_impressions: 90_000, average_cpm: 55_000, budget_vnd: 5_000_000 } },
      verify_order: { result: { order: { id: 'ORD-ACTIVE', status: 'active' } } },
    },
  })
  const report = buildSyntheticPerformance(active)
  assert.equal(report.rows.length, 3)
  assert.equal(report.metrics.impressions, 90_000)
  assert.equal(report.metrics.reach, 30_000)
  assert.equal(report.mode, 'synthetic_showcase')

  const pending = { ...active, orderStatus: 'pending' }
  assert.equal(buildSyntheticPerformance(pending), null)
})
