import test from 'node:test'
import assert from 'node:assert/strict'

import { matchPlannedFormat } from '../src/lib/creativeCompatibility.js'

test('accepts a same-ratio export at different pixel dimensions', () => {
  const match = matchPlannedFormat(
    { name: 'mixifood-znews-masthead.png', width: 928, height: 200 },
    {
      format_id: 'znews-masthead-1160x250',
      width: 1160,
      height: 250,
      intended_format: 'banner',
    },
  )
  assert.equal(match.matched, true)
  assert.match(match.label, /đúng tỷ lệ/)
})

test('requires explicit skin intent even when geometry matches', () => {
  const format = {
    format_id: 'znews-Background',
    width: 1504,
    height: 704,
    intended_format: 'skin',
  }
  assert.equal(matchPlannedFormat(
    { name: 'ordinary-wide.png', width: 1200, height: 562 },
    format,
  ).matched, false)
  assert.equal(matchPlannedFormat(
    { name: 'mixifood-skin.png', width: 1200, height: 562, intendedFormat: 'skin' },
    format,
  ).matched, true)
})

test('a matching filename cannot override an incompatible measured ratio', () => {
  const match = matchPlannedFormat(
    { name: 'mixifood-1160x250.png', width: 300, height: 600 },
    {
      format_id: 'znews-masthead-1160x250',
      width: 1160,
      height: 250,
      intended_format: 'banner',
    },
  )
  assert.equal(match.matched, false)
  assert.match(match.label, /sai tỷ lệ/)
})

test('canonical format identity overrides ratio and keeps an advisory', () => {
  const match = matchPlannedFormat(
    {
      name: 'campaign-smoney-top-desktop.png',
      formatId: 'smoney-top-desktop',
      width: 512,
      height: 512,
    },
    {
      format_id: 'smoney-top-desktop',
      width: 1440,
      height: 108,
      intended_format: 'banner',
    },
  )
  assert.equal(match.matched, true)
  assert.equal(match.identityMatch, true)
  assert.equal(match.ratioAdvisory, true)
  assert.match(match.label, /khớp tên\/format chuẩn/)
})
