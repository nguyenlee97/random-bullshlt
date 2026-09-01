import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('../src/components/CampaignEvaluationWorkspace.jsx', import.meta.url), 'utf8')

test('evaluation exposes persisted specialist progress and honest execution mode', () => {
  assert.match(source, /function InvestigationProgress/)
  assert.match(source, /job\.model_calls/)
  assert.match(source, /job\.attempts/)
  assert.match(source, /job\.tasks/)
  assert.match(source, /deterministic.*multi-agent chưa bật/)
  assert.match(source, /job\.incident_id === i\.incident_id/)
  assert.doesNotMatch(source, /dangerouslySetInnerHTML/)
})

test('polling cleans up and rejects stale campaign responses', () => {
  assert.match(source, /currentCampaign\.current === campaignId/)
  assert.match(source, /sequence === requestSequence\.current/)
  assert.match(source, /clearTimeout\(timer\)/)
  assert.match(source, /if \(!stopped\) timer = setTimeout/)
  assert.match(source, /setData\(result\); setLoadError\(''\)/)
  assert.match(source, /setLoadError\(e\.message\)/)
})

test('evidence source, timestamp, citations and captured screenshot are inspectable', () => {
  assert.match(source, /bundle\.review\.evidence_ids/)
  assert.match(source, /p\.observed_at/)
  assert.match(source, /p\.screenshot_base64/)
  assert.match(source, /chưa chứng minh quan hệ nhân quả/)
})

test('incident Q&A binds revision, preserves request id on retry and suppresses stale responses', () => {
  assert.match(source, /expectedRevision: incident\.dataset_revision/)
  assert.match(source, /expectedBundleId: bundleId/)
  assert.match(source, /request\.current \|\|=/)
  assert.match(source, /currentScope\.current !== submittedScope/)
  assert.match(source, /Kết quả lịch sử, không phải evidence hiện tại/)
  assert.match(source, /a\.citations\.map/)
})

test('investigation distinguishes symptom, scoped cause, limitations and protocol failures', () => {
  for (const field of ['symptom_status', 'cause_status', 'claim_scope', 'limitations', 'error_code', 'validation_errors', 'repairs_used']) {
    assert.ok(source.includes(field), field)
  }
  assert.match(source, /Chưa chốt nguyên nhân/)
  assert.match(source, /Điều tra chưa đầy đủ/)
  assert.match(source, /a\.limitations/)
})
