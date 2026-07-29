const MAX_RATIO_DIFF = 0.15

const FORMAT_BY_CONTRACT = {
  'znews-category-masthead-v1': 'znews-top-banner',
  'baomoi-category-masthead-v1': 'zuma-baomoi-masthead',
  'category-background-v1': 'znews-Background',
  'znews-category-side-left-v1': 'znews-side-banner',
  'znews-category-side-right-v1': 'znews-side-banner',
  'baomoi-category-side-left-v1': 'zuma-Left',
  'baomoi-category-side-right-v1': 'zuma-Right',
  'display-box-300x250-v1': 'zuma-box',
  'display-halfpage-300x600-v1': 'display-halfpage-300x600',
  'znews-home-inline-v1': 'znews-middle-banner',
  'zingmp3-masthead-v1': 'zmp3-top-banner',
  'smoney-top-desktop-v1': 'smoney-top-desktop',
  'smoney-top-mobile-v1': 'smoney-top-mobile',
  'smoney-screener-desktop-v1': 'smoney-screener-desktop',
  'smoney-screener-mobile-v1': 'smoney-screener-mobile',
  'dicungcon-bridge-desktop-v1': 'dicungcon-bridge-desktop',
  'dicungcon-bridge-mobile-v1': 'dicungcon-bridge-mobile',
  'zagoo-interstitial-desktop-v1': 'zagoo-interstitial-desktop',
  'zagoo-interstitial-mobile-v1': 'zagoo-interstitial-mobile',
}

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
  FORMAT_BY_CONTRACT[candidate.creativeContractId]
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
export function compatiblePlacementIndexes(candidates = [], creativeFormats = [], keep = 2) {
  const limit = Math.max(1, Number(keep || 2))
  const ranked = candidates
    .map((candidate, index) => ({
      index,
      score: compatibilityScore(candidate, creativeFormats),
    }))
    .filter(item => Number.isFinite(item.score))
    .sort((left, right) => right.score - left.score || left.index - right.index)
  return ranked.slice(0, limit).map(item => item.index)
}

