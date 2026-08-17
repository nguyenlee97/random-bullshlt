export const AUTOPILOT_CHECKPOINT_OBSERVATION = Object.freeze({
  EXPECTED: 'expected',
  STALE_PREVIOUS: 'stale_previous',
  UNEXPECTED: 'unexpected',
  TERMINAL: 'terminal',
  PENDING: 'pending',
})

/**
 * Classify the task currently exposed by the Autopilot canvas.
 *
 * After a checkpoint is approved, the UI can keep reporting that same
 * `waiting_review` task while the backend resumes and reaches the next task.
 * That is a normal transition, not a newly-created checkpoint.
 */
export function classifyAutopilotCheckpointObservation({
  expectedTaskKeys = [],
  taskKey = '',
  status = '',
  lastHandledTask = '',
}) {
  if (expectedTaskKeys.includes(taskKey)) {
    return AUTOPILOT_CHECKPOINT_OBSERVATION.EXPECTED
  }

  if (['failed', 'cancelled'].includes(status)) {
    return AUTOPILOT_CHECKPOINT_OBSERVATION.TERMINAL
  }

  if (status === 'waiting_review' && taskKey) {
    if (taskKey === lastHandledTask) {
      return AUTOPILOT_CHECKPOINT_OBSERVATION.STALE_PREVIOUS
    }
    return AUTOPILOT_CHECKPOINT_OBSERVATION.UNEXPECTED
  }

  return AUTOPILOT_CHECKPOINT_OBSERVATION.PENDING
}
