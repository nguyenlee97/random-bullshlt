import { FORMAT_BY_CREATIVE_CONTRACT } from '../lib/creativeAssignmentIdentity.js'

const MAX_RATIO_DIFF = 0.15

const FORMAT_BY_SIZE = {
  '300x250': 'zuma-box',
  '300x600': 'display-halfpage-300x600',
  '1160x250': 'znews-masthead-1160x250',
  '1160x280': 'zuma-baomoi-masthead',
  '2032x528': 'zmp3-top-banner',
}

const normalizedSize = value => String(value || '')
  .toLowerCase()
  .replace('×', 'x')
  .replaceAll(' ', '')

const dimensions = value => {
  const match = normalizedSize(value).match(/^(\d+)x(\d+)$/)
  return match ? [Number(match[1]), Number(match[2])] : null
}

const formatForCandidate = candidate => (
  FORMAT_BY_CREATIVE_CONTRACT[candidate.creativeContractId]
  || FORMAT_BY_SIZE[normalizedSize(candidate.size)]
  || ''
)

const compatibilityScore = (candidate, creativeFormats) => {
  const formatId = formatForCandidate(candidate)
  const exact = creativeFormats.find(item => item.formatId === formatId)
  if (exact) return 10_000

  const targetDims = dimensions(candidate.size)
  if (!targetDims || normalizedSize(candidate.size) === 'skin') return -Infinity
  const [targetWidth, targetHeight] = targetDims
  const targetRatio = targetWidth / targetHeight
  const bestDiff = creativeFormats.reduce((best, item) => {
    const width = Number(item.width || 0)
    const height = Number(item.height || 0)
    if (!width || !height || item.intendedFormat === 'skin') return best
    const ratioDiff = Math.abs(targetRatio - (width / height)) / targetRatio
    return Math.min(best, ratioDiff)
  }, Infinity)
  return bestDiff < MAX_RATIO_DIFF ? 1_000 - (bestDiff * 1_000) : -Infinity
}

/**
 * Pick at most `keep` candidate indexes that an uploaded walkthrough creative
 * can safely cover. Original recommendation order breaks compatibility ties.
 */
export function samplePlacementIndexes(indexes = [], keep = 2, random = Math.random) {
  const pool = [...new Set(indexes)]
  for (let index = pool.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1))
    ;[pool[index], pool[swapIndex]] = [pool[swapIndex], pool[index]]
  }
  return pool.slice(0, Math.max(0, Math.min(Number(keep || 0), pool.length)))
}

export function supportedPlacementIndexes(candidates = [], keep = 2, random = Math.random) {
  const eligible = candidates
    .map((candidate, index) => ({ candidate, index }))
    .filter(({ candidate }) => (
      Boolean(formatForCandidate(candidate))
      || Boolean(dimensions(candidate.size))
    ))
    .map(item => item.index)
  return samplePlacementIndexes(eligible, keep, random)
}

export function compatiblePlacementIndexes(
  candidates = [],
  creativeFormats = [],
  keep = 2,
  random = Math.random,
) {
  const limit = Math.max(1, Number(keep || 2))
  const ranked = candidates
    .map((candidate, index) => ({
      index,
      score: compatibilityScore(candidate, creativeFormats),
    }))
    .filter(item => Number.isFinite(item.score))
    .sort((left, right) => right.score - left.score || left.index - right.index)
  const compatible = samplePlacementIndexes(
    ranked.map(item => item.index),
    limit,
    random,
  )
  if (compatible.length >= limit) return compatible
  const selected = new Set(compatible)
  const fallback = supportedPlacementIndexes(
    candidates.map((candidate, index) => (
      selected.has(index) ? {} : candidate
    )),
    limit - compatible.length,
    random,
  )
  return [...compatible, ...fallback]
}
