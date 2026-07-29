export function partitionConversationHistory(conversations = []) {
  return {
    active: conversations.filter(conversation => !conversation?.archived_at),
    archived: conversations.filter(conversation => Boolean(conversation?.archived_at)),
  }
}
