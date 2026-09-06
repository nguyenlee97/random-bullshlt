export const DESKTOP_CAMPAIGN_PAGE_SIZES = Object.freeze({
  attention: 4,
  drafts: 6,
  live: 2,
  completed: 4,
  archive: 4,
})

export const isOperationalCampaign = item => item?.phase === 'operational'
  || ['operational', 'active', 'paused', 'scheduled', 'completed', 'failed'].includes(item?.lifecycle)

export const isCompletedCampaign = item => item?.lifecycle === 'completed'

export const isLiveCampaign = item => ['operational', 'active', 'paused'].includes(item?.lifecycle)

export const campaignPageSize = (groupId, compact = false) => compact
  ? 1
  : DESKTOP_CAMPAIGN_PAGE_SIZES[groupId] || 2
