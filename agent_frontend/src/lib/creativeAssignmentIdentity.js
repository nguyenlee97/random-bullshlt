const compactIdentity = (value) =>
  String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '')

export const FORMAT_BY_CREATIVE_CONTRACT = {
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

const combinedFileIdentity = (file = {}) => compactIdentity([
  file.name,
  file.formatId,
  file.intendedFormat,
].filter(Boolean).join(' '))

const combinedZoneIdentity = (zone = {}) => compactIdentity([
  zone.id,
  zone.name,
  zone.platform,
  zone.channel,
  zone.placement,
  zone.creativeContractId,
].filter(Boolean).join(' '))

export function assignmentPlatform(value) {
  const identity = compactIdentity(value)
  if (!identity) return ''
  if (
    identity.includes('znews')
    || identity.includes('zingnews')
    || identity.startsWith('zn')
  ) return 'znews'
  if (
    identity.includes('baomoi')
    || identity.includes('zuma')
    || identity.startsWith('bm')
  ) return 'baomoi'
  if (identity.includes('zingmp3') || identity.includes('zmp3')) return 'zmp3'
  return ''
}

export function assignmentRole(value) {
  const identity = compactIdentity(value)
  if (!identity) return ''
  if (
    identity.includes('sideleft')
    || identity.includes('stickyleft')
    || identity.endsWith('left')
  ) return 'side_left'
  if (
    identity.includes('sideright')
    || identity.includes('stickyright')
    || identity.endsWith('right')
  ) return 'side_right'
  if (
    identity.includes('sidebanner')
    || identity.includes('skyscraper')
  ) return 'side'
  if (identity.includes('background') || identity.includes('roadblock')) {
    return 'background'
  }
  if (
    identity.includes('masthead')
    || identity.includes('topbanner')
    || identity.includes('topdesktop')
    || identity.includes('topmobile')
  ) return 'masthead'
  if (
    identity.includes('sidebarbox')
    || identity.includes('box300x250')
    || identity.includes('zumabox')
  ) return 'box'
  return ''
}

function roleScore(zoneRole, fileRole) {
  if (!zoneRole || !fileRole) return 0
  if (zoneRole === fileRole) return 12
  if (
    (zoneRole === 'side_left' || zoneRole === 'side_right')
    && fileRole === 'side'
  ) return 12
  if (
    zoneRole === 'side'
    && (fileRole === 'side_left' || fileRole === 'side_right')
  ) return 10
  if (
    (zoneRole === 'side_left' && fileRole === 'side_right')
    || (zoneRole === 'side_right' && fileRole === 'side_left')
  ) return -30
  return -20
}

/**
 * Score explicit creative identity independently from measured geometry.
 *
 * A known cross-platform mismatch is a hard negative so a ZNews placement
 * cannot silently receive a BaoMoi/ZUMA asset (and vice versa). Generic file
 * names remain neutral, allowing measured geometry to act as a safe fallback.
 */
export function creativeAssignmentIdentityScore(file = {}, zone = {}) {
  const fileIdentity = combinedFileIdentity(file)
  const zoneIdentity = combinedZoneIdentity(zone)
  const filePlatform = assignmentPlatform(fileIdentity)
  const zonePlatform = assignmentPlatform(zoneIdentity)
  const fileRole = assignmentRole(fileIdentity)
  const zoneRole = assignmentRole(zoneIdentity)

  let score = 0
  if (filePlatform && zonePlatform) {
    score += filePlatform === zonePlatform ? 12 : -40
  }
  score += roleScore(zoneRole, fileRole)
  return score
}

export function highConfidenceCreativeIdentity(file = {}, zone = {}) {
  const formatId = FORMAT_BY_CREATIVE_CONTRACT[zone.creativeContractId] || ''
  if (!formatId) return false
  const filename = compactIdentity(file.name)
  const formatHint = compactIdentity(formatId)
  return file.formatId === formatId
    || Boolean(formatHint && filename.includes(formatHint))
}

export function bestCreativeForZone(files = [], zone = {}) {
  return [...files]
    .map((file, index) => ({
      file,
      index,
      score: highConfidenceCreativeIdentity(file, zone)
        ? 100
        : creativeAssignmentIdentityScore(file, zone),
    }))
    .sort((left, right) =>
      right.score - left.score || left.index - right.index
    )
    .at(0)?.file || null
}
