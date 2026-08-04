export const MAX_CONCURRENT_GENERATIONS = 2
export const MAX_PENDING_GENERATIONS = 5

const ACTIVE_GENERATION_STATUSES = new Set(['generating', 'reserved'])
const PENDING_GENERATION_STATUSES = new Set(['queued', ...ACTIVE_GENERATION_STATUSES])

export function isActiveGeneration(job) {
  return ACTIVE_GENERATION_STATUSES.has(job?.status)
}

export function isPendingGeneration(job) {
  return PENDING_GENERATION_STATUSES.has(job?.status)
}

export function countActiveGenerations(jobs = []) {
  return jobs.filter(isActiveGeneration).length
}

export function countPendingGenerations(jobs = []) {
  return jobs.filter(isPendingGeneration).length
}

export function canEnqueueGeneration(jobs = []) {
  return countPendingGenerations(jobs) < MAX_PENDING_GENERATIONS
}

export function nextQueuedGenerations(jobs = []) {
  const openSlots = Math.max(0, MAX_CONCURRENT_GENERATIONS - countActiveGenerations(jobs))
  if (openSlots === 0) return []
  return jobs.filter(job => job?.status === 'queued').slice(0, openSlots)
}
