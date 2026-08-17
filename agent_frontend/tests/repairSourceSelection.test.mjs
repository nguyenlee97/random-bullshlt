import test from 'node:test'
import assert from 'node:assert/strict'

import { selectRepairSourceFile } from '../src/lib/creativeCompatibility.js'

test('repair source selection prefers canonical formatId over file order', () => {
  const format = {
    format_id: 'znews-Background',
    width: 1504,
    height: 704,
  }
  const first = {
    name: 'first-upload.png',
    width: 1504,
    height: 704,
  }
  const intended = {
    name: 'campaign-hero.png',
    formatId: 'znews-Background',
    width: 1200,
    height: 562,
  }

  assert.equal(selectRepairSourceFile([first, intended], format), intended)
})

test('repair source selection recognizes a format encoded in the filename', () => {
  const format = {
    format_id: 'znews-Background',
    width: 1504,
    height: 704,
  }
  const first = {
    name: 'first-upload.png',
    width: 1504,
    height: 704,
  }
  const named = {
    name: 'ai-znews-Background-cafe1234.png',
    width: 1200,
    height: 562,
  }

  assert.equal(selectRepairSourceFile([first, named], format), named)
})

test('repair source selection falls back to ratio then resolution', () => {
  const format = {
    format_id: 'znews-middle-banner',
    width: 2048,
    height: 512,
  }
  const smaller = {
    name: 'small.png',
    width: 1024,
    height: 256,
  }
  const exact = {
    name: 'exact.png',
    width: 2048,
    height: 512,
  }

  assert.equal(selectRepairSourceFile([smaller, exact], format), exact)
})
