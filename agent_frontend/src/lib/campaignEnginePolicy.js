export const ACTIVE_CAMPAIGN_ENGINE_ID = 'openai_gpt_5_4_mini'

export const CAMPAIGN_ENGINE_UNAVAILABLE_MESSAGE =
  'Campaign Agent tạm thời chưa sẵn sàng. Vui lòng thử lại sau.'

export function resolveActiveCampaignEngine(catalog) {
  const models = Array.isArray(catalog?.models) ? catalog.models : []
  const activeEngine = models.find(item => item.id === ACTIVE_CAMPAIGN_ENGINE_ID)
  return activeEngine?.available ? activeEngine.id : ''
}

export function isActiveCampaignEngine(modelId) {
  return modelId === ACTIVE_CAMPAIGN_ENGINE_ID
}
