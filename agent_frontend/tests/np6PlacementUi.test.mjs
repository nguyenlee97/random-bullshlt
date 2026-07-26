import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(path.join(here, '..', 'src', 'steps', 'setup', 'ZoneSelectionPhase.jsx'), 'utf8')

test('placement previews use the production-facing label', () => {
  assert.match(source, /Xem ad placement/)
  assert.doesNotMatch(source, /Xem mock placement/)
})

test('publisher filter is derived from the live catalog', () => {
  assert.match(source, /const publisherOptions = useMemo/)
  assert.match(source, /\.map\(\(zone\) => zone\.publisher \|\| zone\.platform \|\| zone\.siteId\)/)
  assert.match(source, /publisherOptions\.map/)
  assert.doesNotMatch(source, /<option value="ZNews">/)
})

test('placement cards disclose semantic RAG evidence', () => {
  assert.match(source, /RAG semantic khớp brief\/audience/)
  assert.match(source, /recommendation_relevance/)
  assert.match(source, /topic_rerank_rank/)
})
