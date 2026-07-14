/**
 * Centralized frontend logger for Advertising Agent.
 * All log lines are prefixed with a category tag for easy filtering in DevTools.
 *
 * Usage:
 *   import log from '@/lib/logger'
 *   log.api('callAgent', { req, res })
 *   log.chat('sendMessage', { text, step })
 *   log.workspace('update', { patch })
 *
 * Filter in Chrome DevTools console: type the prefix, e.g. "[API]", "[WORKSPACE]"
 */

const IS_DEV = import.meta.env.DEV || window.location.hostname === 'localhost'

// Style map per category
const STYLES = {
  API:       'background:#1e40af;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  CHAT:      'background:#059669;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  WORKSPACE: 'background:#d97706;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  STEP:      'background:#7c3aed;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  EVENT:     'background:#db2777;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  BLOCK:     'background:#0891b2;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  FORM:      'background:#4f46e5;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  ERROR:     'background:#dc2626;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  INFO:      'background:#6b7280;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
}

function _log(category, action, payload, level = 'log') {
  const style = STYLES[category] || STYLES.INFO
  const ts = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 })

  if (payload !== undefined) {
    console.groupCollapsed(`%c${category}%c ${action}  %c${ts}`, style, 'color:inherit', 'color:#9ca3af;font-size:10px')
    if (level === 'error') {
      console.error(payload)
    } else {
      console.log(payload)
    }
    console.groupEnd()
  } else {
    console[level](`%c${category}%c ${action}  %c${ts}`, style, 'color:inherit', 'color:#9ca3af;font-size:10px')
  }
}

const log = {
  /** API calls to backend agent */
  api: (action, payload) => _log('API', action, payload),

  /** Chat hook events (sendMessage, approveStep, boot) */
  chat: (action, payload) => _log('CHAT', action, payload),

  /** Workspace state changes (formState diffs, patches) */
  workspace: (action, payload) => _log('WORKSPACE', action, payload),

  /** Step transitions and approvals */
  step: (action, payload) => _log('STEP', action, payload),

  /** DOM/custom events (agent:reset, agent:workspace_confirm, etc.) */
  event: (action, payload) => _log('EVENT', action, payload),

  /** Block rendering (workspace_proposal, action_reset) */
  block: (action, payload) => _log('BLOCK', action, payload),

  /** Form field changes on Workspace panel */
  form: (action, payload) => _log('FORM', action, payload),

  /** Errors */
  error: (action, payload) => _log('ERROR', action, payload, 'error'),

  /** Generic info */
  info: (action, payload) => _log('INFO', action, payload),
}

export default log
