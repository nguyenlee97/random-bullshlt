const AUTOPILOT_TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled'])

export function ongoingAutopilotConversations(conversations = []) {
  return conversations.filter(conversation => {
    const status = conversation?.latest_run_summary?.status
    return Boolean(status && !AUTOPILOT_TERMINAL_STATUSES.has(status))
  })
}
