import assert from 'node:assert/strict'
import test from 'node:test'

import {
  foldCatalogText,
  matchesCatalogSearch,
} from '../src/lib/catalogSearch.js'

test('catalog search folds Vietnamese accents and đ', () => {
  assert.equal(foldCatalogText('Ô tô, Di chuyển'), 'o to, di chuyen')
  assert.equal(matchesCatalogSearch(['Sức khỏe & Wellness'], 'suc khoe'), true)
})

test('catalog search covers topic, format, and dimensions', () => {
  const values = ['Automotive Mobility', 'Masthead', '1160×250', 'ZNews']
  assert.equal(matchesCatalogSearch(values, 'automotive'), true)
  assert.equal(matchesCatalogSearch(values, '1160x250'), true)
  assert.equal(matchesCatalogSearch(values, '1160×250'), true)
  assert.equal(matchesCatalogSearch(values, 'masthead'), true)
})
