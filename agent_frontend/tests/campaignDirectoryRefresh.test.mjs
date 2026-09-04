import test from 'node:test'
import assert from 'node:assert/strict'
import { loadCampaignDirectory } from '../src/lib/campaignDirectoryRefresh.js'

test('selected campaign survives repeated capped directory polls', async () => {
  const page = Array.from({ length: 50 }, (_, i) => ({ entry_id: `draft:${i}` }))
  let revision = 0
  const api = {
    listCampaigns: async () => page,
    getCampaign: async id => ({ campaign_id: id, revision: ++revision }),
  }
  for (let i = 1; i <= 3; i++) {
    const result = await loadCampaignDirectory(api, 'QA')
    assert.equal(result.length, 51)
    assert.deepEqual(result[0], { campaign_id: 'QA', revision: i })
  }
})

test('refresh removes revoked campaign even if capped page still contains it', async () => {
  const api = {
    listCampaigns: async () => [{ campaign_id: 'QA' }],
    getCampaign: async () => { throw Object.assign(new Error('not found'), { status: 404 }) },
  }
  assert.deepEqual(await loadCampaignDirectory(api, 'QA'), [])
})

test('transient detail failure is not silently treated as missing campaign', async () => {
  const api = {
    listCampaigns: async () => [],
    getCampaign: async () => { throw new Error('timeout') },
  }
  await assert.rejects(loadCampaignDirectory(api, 'QA'), /timeout/)
})

test('homepage does not request a selected campaign', async () => {
  const page = [{ campaign_id: 'A' }]
  assert.equal(await loadCampaignDirectory({ listCampaigns: async () => page }), page)
})
