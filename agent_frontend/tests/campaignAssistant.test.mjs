import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('../src/components/CampaignManagement.jsx', import.meta.url), 'utf8')
const apiSource = await readFile(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')

test('Campaign Agent sends recent context and renders semantic read-only follow-ups', () => {
  assert.match(source, /messages\.slice\(-8\)/)
  assert.match(source, /askCampaignAssistant\(campaignId, clean, history\)/)
  assert.match(source, /suggestions: result\.suggestions \|\| \[\]/)
  assert.match(source, /message\.suggestions\?\.length > 0/)
  assert.doesNotMatch(source, /dangerouslySetInnerHTML/)
  assert.match(apiSource, /JSON\.stringify\(\{ question, history \}\)/)
  assert.match(apiSource, /AbortSignal\.timeout\(120000\)/)
})
