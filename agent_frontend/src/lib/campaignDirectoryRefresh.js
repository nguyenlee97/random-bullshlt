// Re-resolve the selected entry on every refresh: a capped homepage response
// cannot establish that a campaign is missing or that ownership was revoked.
export async function loadCampaignDirectory(api, campaignId = '') {
  const [items, selected] = await Promise.all([
    api.listCampaigns(true),
    campaignId ? api.getCampaign(campaignId).catch(error => {
      if (error.status === 404) return null
      throw error
    }) : Promise.resolve(null),
  ])
  if (!campaignId) return items
  const others = items.filter(item => item.campaign_id !== campaignId)
  return selected ? [selected, ...others] : others
}
