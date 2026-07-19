import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  creativeReviewState,
  defaultPlacementSelection,
  mergeCreativeVerdicts,
} from '../src/lib/creativeIntel.js'

test('creative review separates analysis completion from operator confirmation', () => {
  assert.equal(creativeReviewState([{ analysisStatus: 'queued' }]), 'analysis_required')
  assert.equal(creativeReviewState([{ analysisStatus: 'needs_review' }]), 'blocked')
  assert.equal(creativeReviewState([
    { analysisStatus: 'auto_approved' },
    { analysisStatus: 'approved_override' },
  ]), 'ready')
})

test('hydrates queued creative files with canonical terminal verdicts', () => {
  const creative = {
    files: [{ id: 'f1', name: 'banner.png', url: '/uploads/banner.png', analysisStatus: 'queued' }],
  }
  const merged = mergeCreativeVerdicts(creative, {
    files: [{
      analysis_id: 'ci-1',
      name: 'banner.png',
      url: '/uploads/banner.png',
      status: 'needs_review',
      effective_status: 'approved_override',
      deterministic: { width: 1200, height: 628 },
      override: { approved: true },
    }],
  })

  assert.equal(merged.files[0].analysisStatus, 'approved_override')
  assert.equal(merged.files[0].analysisId, 'ci-1')
  assert.equal(merged.files[0].width, 1200)
})

test('recovers older canonical snapshots that captured a transient commit status', () => {
  const merged = mergeCreativeVerdicts({
    files: [{ name: 'banner.png', url: '/uploads/banner.png', analysisStatus: 'queued' }],
  }, {
    files: [{
      name: 'banner.png',
      url: '/uploads/banner.png',
      status: 'needs_review',
      effective_status: 'committing',
      review_reasons: ['VLM không khả dụng'],
    }],
  })
  assert.equal(merged.files[0].analysisStatus, 'needs_review')
})

test('placement review displays the shortlist but defaults to top six', () => {
  const value = { candidate_zone_ids: Array.from({ length: 12 }, (_, index) => `zone-${index + 1}`) }
  assert.deepEqual(defaultPlacementSelection(value), value.candidate_zone_ids.slice(0, 6))
})

test('completed Copilot creative view keeps the full analysis visible', () => {
  const source = readFileSync(new URL('../src/steps/CreativeStep.jsx', import.meta.url), 'utf8')
  assert.match(source, /Kết quả phân tích Creative Intelligence/)
  assert.match(source, /Creative đã được phân tích và duyệt/)
  assert.match(source, /Khớp brief:/)
  assert.match(source, /Độ tin cậy:/)
  assert.match(source, /Không phát hiện nhóm nội dung nhạy cảm/)
  assert.match(source, /Phê duyệt có lý do/)
})
