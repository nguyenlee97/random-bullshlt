export const OPENAI_CAMPAIGN_MODEL = 'openai_gpt_5_4_mini'

const OPENAI_WALKTHROUGH_TOOL_ALIASES = {
  openai_audience_entry: 'audience_entry',
  openai_setup_entry: 'setup_entry',
}

export function isOpenAIWalkthroughModel(conversationModel) {
  return conversationModel === OPENAI_CAMPAIGN_MODEL
}

export function matchesWalkthroughMetaTool(conversationModel, actualTool, expectedTool) {
  if (actualTool === expectedTool) return true
  if (!isOpenAIWalkthroughModel(conversationModel)) return false
  return OPENAI_WALKTHROUGH_TOOL_ALIASES[actualTool] === expectedTool
}

export function rememberOpenAIWalkthroughTool(seenTools, conversationModel, event) {
  if (!isOpenAIWalkthroughModel(conversationModel)) return false
  const actualTool = event?.detail?.metadata?.tool
  if (!actualTool) return false
  const semanticTool = OPENAI_WALKTHROUGH_TOOL_ALIASES[actualTool] || actualTool
  seenTools.add(semanticTool)
  return true
}

export function hasSeenOpenAIWalkthroughTool(seenTools, conversationModel, metaTool) {
  return isOpenAIWalkthroughModel(conversationModel) && seenTools.has(metaTool)
}
