import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  calcAudienceSize,
  dedupeDmpAttrs,
  enrichAudienceSelection,
  hasKnownAudienceSize,
  normalizeAudienceSelection,
  normalizeDmpAttr,
} from '../src/lib/audience.js'

test('normalizes raw Autopilot audience segments for the guided picker', () => {
  const normalized = normalizeDmpAttr({
    _id: 'mongo-id',
    segmentId: 'INT158',
    fullLabel: 'Fast food (food & drink)',
    category: 'Food and drink',
    sizeMin: 100,
    sizeMax: 300,
  })

  assert.equal(normalized._uid, 'INT158')
  assert.equal(normalized.code, 'INT158')
  assert.equal(normalized.name, 'Fast food (food & drink)')
  assert.equal(normalized.est_size, 200)
  assert.equal(normalized._id, 'mongo-id')
})

test('recalculates missing Autopilot audience size from normalized segments', () => {
  const audience = normalizeAudienceSelection({
    attrs: [
      { segmentId: 'A', fullLabel: 'A', sizeMin: 1000, sizeMax: 1000 },
      { segmentId: 'B', fullLabel: 'B', sizeMin: 500, sizeMax: 500 },
    ],
  })

  assert.deepEqual(audience.attrs.map(attr => attr._uid), ['A', 'B'])
  assert.equal(audience.size, calcAudienceSize(audience.attrs))
  assert.equal(audience.size, 1350)
})

test('enriches an older Autopilot selection from the current catalog', () => {
  const audience = enrichAudienceSelection(
    { attrs: [{ segmentId: 'INT158', fullLabel: 'Fast food', reason: 'Relevant' }], size: 0 },
    [{ segmentId: 'INT158', fullLabel: 'Fast food', sizeMin: 1000, sizeMax: 3000 }],
  )

  assert.equal(audience.attrs[0]._uid, 'INT158')
  assert.equal(audience.attrs[0].reason, 'Relevant')
  assert.equal(audience.attrs[0].est_size, 2000)
  assert.equal(audience.size, 2000)
})

test('deduplicates legacy and provider recommendations by stable catalog ID', () => {
  const attrs = dedupeDmpAttrs([
    { segmentId: 'INT158', fullLabel: 'Fast food', reason: 'first' },
    { segmentId: 'INT158', fullLabel: 'Fast food', reason: 'duplicate' },
    { segmentId: 'INT157', fullLabel: 'Desserts' },
  ])

  assert.deepEqual(attrs.map(attr => attr._uid), ['INT158', 'INT157'])
  assert.equal(attrs[0].reason, 'first')
})

test('normalizing a stored audience removes duplicate IDs before rendering', () => {
  const audience = normalizeAudienceSelection({
    attrs: [
      { segmentId: 'INT158', fullLabel: 'Fast food' },
      { segmentId: 'INT158', fullLabel: 'Fast food' },
    ],
  })

  assert.equal(audience.attrs.length, 1)
})

test('catalog segments without size remain unknown instead of becoming a zero audience', () => {
  const audience = normalizeAudienceSelection({
    attrs: [{ segmentId: 'INT158', fullLabel: 'Fast food' }],
  })

  assert.equal(hasKnownAudienceSize(audience.attrs), false)
  assert.equal(audience.size, 0)
  assert.equal(audience.sizeKnown, false)
})
