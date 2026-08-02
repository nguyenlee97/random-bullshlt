import assert from 'node:assert/strict'
import test from 'node:test'

import {
  assignCreativeImageSource,
  creativeImageCrossOrigin,
  creativeImageSource,
} from '../src/lib/creativeImageUrl.js'

test('production upload URLs remain on the backend host', () => {
  const url = 'https://api.pawgrammers.io.vn/uploads/creative_ai_example.png'
  assert.equal(creativeImageSource(url), url)
  assert.equal(creativeImageCrossOrigin(url), 'anonymous')
})

test('same-origin upload paths and data URLs remain valid sources', () => {
  assert.equal(creativeImageSource('/uploads/creative_ai_example.png'), '/uploads/creative_ai_example.png')
  assert.equal(creativeImageCrossOrigin('/uploads/creative_ai_example.png'), undefined)
  assert.equal(creativeImageSource('data:image/png;base64,abc123'), 'data:image/png;base64,abc123')
})

test('legacy raw base64 is wrapped and remote canvas images enable CORS first', () => {
  assert.equal(creativeImageSource('abc123'), 'data:image/png;base64,abc123')
  const image = {}
  const url = 'https://api.pawgrammers.io.vn/uploads/creative_ai_example.png'
  assert.equal(assignCreativeImageSource(image, url), url)
  assert.equal(image.crossOrigin, 'anonymous')
  assert.equal(image.src, url)
})
