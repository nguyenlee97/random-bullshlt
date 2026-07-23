export const OPENAI_CAMPAIGN_MODEL = 'openai_gpt_5_4_mini'

export function isOpenAIWalkthroughModel(conversationModel) {
  return conversationModel === OPENAI_CAMPAIGN_MODEL
}

export function rememberOpenAIWalkthroughTool(seenTools, conversationModel, event) {
  if (!isOpenAIWalkthroughModel(conversationModel)) return false
  const tool = event?.detail?.metadata?.tool
  if (!tool) return false
  seenTools.add(tool)
  return true
}

export function hasSeenOpenAIWalkthroughTool(seenTools, conversationModel, metaTool) {
  return isOpenAIWalkthroughModel(conversationModel) && seenTools.has(metaTool)
}
