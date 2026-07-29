import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(path.join(here, '..', 'src', 'steps', 'setup', 'ZoneSelectionPhase.jsx'), 'utf8')
const assignmentSource = fs.readFileSync(path.join(here, '..', 'src', 'steps', 'setup', 'CreativeAssignPhase.jsx'), 'utf8')

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

test('OpenAI placement editor exposes related zones and catalog controls', () => {
  assert.match(source, /data-demo="related-zones-section"/)
  assert.match(source, /relatedZones\.map/)
  assert.match(source, /topicFilter/)
  assert.match(source, /expandedTopics/)
  assert.match(source, /aria-expanded=\{topicExpanded\}/)
  assert.match(source, /matchesCatalogSearch/)
})

test('placement continue action remains sticky below the catalog', () => {
  assert.match(source, /sticky bottom-0/)
  assert.match(source, /id="confirm-zones-btn"/)
})

test('OpenAI Guided auto-assign rejects incompatible creative ratios', () => {
  assert.match(assignmentSource, /strictCompatibility = repairMode \|\| openaiCampaignFlow/)
  assert.match(assignmentSource, /approvedFiles\.filter\(file => !checkAutopilotMismatch\(zone, file\)\)/)
  assert.match(assignmentSource, /else delete newAssignments\[zone\.id\]/)
})
