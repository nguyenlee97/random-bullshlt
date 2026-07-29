import { ALL_ZONES } from '@/data/zones'
import {
  creativeAssignmentIdentityScore,
  highConfidenceCreativeIdentity,
} from '@/lib/creativeAssignmentIdentity'

// ─── Parse size string — handles both 'x' (DB format) and '×' (display format)
function _parseDims(sizeStr) {
  if (!sizeStr) return null
  const m = String(sizeStr).match(/^(\d+)[x×](\d+)$/i)
  return m ? [parseInt(m[1], 10), parseInt(m[2], 10)] : null
}

// ─── Returns true if the zone has a real parseable pixel size (not 'skin') ─────
export function canCheckRatio(zone) {
  return !!_parseDims(zone?.size)
}

// ─── Ratio mismatch check ─────────────────────────────────────────────────────
// Returns:
//   string  — mismatch warning (ratio > 15% off)
//   false   — explicitly checked and ratio is OK  ← use this to show green ✓
//   null    — can't check (no file dims, or zone size is 'skin' / unparseable)
export function checkMismatch(zone, file) {
  if (!file?.width || !file?.height) return null
  const dims = _parseDims(zone?.size)
  if (!dims) return null                          // skin or non-parseable — skip
  const [zw, zh] = dims
  const zRatio = zw / zh
  const fRatio = file.width / file.height

  // Same orientation (both portrait or both landscape): ad servers can stretch/fit,
  // so allow up to 45% ratio diff before warning.
  // Cross-orientation (portrait zone vs landscape image or vice versa): warn at 30%.
  const sameOrientation = (zw >= zh) === (file.width >= file.height)
  const threshold = sameOrientation ? 0.45 : 0.30

  if (Math.abs(zRatio - fRatio) / zRatio > threshold) {
    const zLabel = zw > zh ? 'ngang' : 'dọc'
    const fLabel = file.width > file.height ? 'ngang' : 'dọc'
    return `Zone ${zone.size} (${zLabel}) · Ảnh ${file.width}×${file.height}px (${fLabel})`
  }
  return false                                    // explicitly OK
}

// Autopilot uses the server's launch-safe 15% ratio boundary. Keep the looser
// Guided warning band above unchanged for the legacy/GreenNode setup flow.
export function checkAutopilotMismatch(zone, file) {
  if (!file?.width || !file?.height) return null
  if (highConfidenceCreativeIdentity(file, zone)) return false
  const dims = _parseDims(zone?.size)
  if (!dims) return null
  const [zoneWidth, zoneHeight] = dims
  const zoneRatio = zoneWidth / zoneHeight
  const fileRatio = file.width / file.height
  const ratioDiff = Math.abs(zoneRatio - fileRatio) / zoneRatio
  if (ratioDiff < 0.15) return false
  const zoneLabel = zoneWidth > zoneHeight ? 'ngang' : 'dọc'
  const fileLabel = file.width > file.height ? 'ngang' : 'dọc'
  return `Zone ${zone.size} (${zoneLabel}) · Ảnh ${file.width}×${file.height}px (${fileLabel})`
}


// ─── Smart score: how well a file fits a zone ─────────────────────────────────
export function scoreFile(file, zone, { identityAware = false } = {}) {
  let score = 0
  const fname = (file.name || '').toLowerCase()
  const format = (zone.format || '').toLowerCase()
  const dims = _parseDims(zone?.size)
  const canonicalIdentity = identityAware
    && highConfidenceCreativeIdentity(file, zone)

  // ─── 1. Canonical identity — platform + placement role/direction.
  // Known cross-platform or left/right conflicts are hard negatives. Generic
  // names stay neutral so measured geometry can still provide a safe fallback.
  if (canonicalIdentity) score += 100
  else if (identityAware) score += creativeAssignmentIdentityScore(file, zone)

  // ─── 2. Generic skin hint. This is deliberately weaker than platform and
  // role identity: a filename containing "skin" is not enough to prove that a
  // BaoMoi asset belongs on ZNews, or that a Left asset belongs on SideRight.
  if (format === 'skin') {
    score += identityAware
      ? (fname.includes('skin') ? 4 : 0)
      : (fname.includes('skin') ? 12 : -6)
  }

  // ─── 3. Orientation match — portrait vs landscape (±10)
  if (dims && file.width && file.height) {
    const [zw, zh] = dims
    const zPortrait = zh > zw
    const fPortrait = file.height > file.width
    score += zPortrait === fPortrait ? 10 : -10
  }

  // ─── 4. Aspect ratio closeness (only within same orientation)
  if (dims && file.width && file.height) {
    const [zw, zh] = dims
    const diff = Math.abs((zw / zh) - (file.width / file.height)) / (zw / zh)
    if (diff < 0.02)       score += 8
    else if (diff < 0.08)  score += 4
    else if (diff < 0.15)  score += 1
    else                   score -= 3 + Math.round(diff * 100)
  }

  // ─── 5. Size string in filename (+5)
  if (zone.size && format !== 'skin') {
    const sNorm = zone.size.replace(/[x×]/i, 'x')
    if (fname.includes(sNorm) || fname.includes(sNorm.replace('x', '_'))) score += 5
  }

  return score
}

// ─── Get selectedZones array from IDs ─────────────────────────────────────────
// Merges three sources, in priority order for display fields:
//   1. recoZones  — backend zones (have matching backend IDs + fresh metrics)
//   2. allZones   — extended catalog passed by parent (may be static or fallback zones)
//   3. ALL_ZONES  — static frontend catalog (dot-notation IDs, rich display fields)
// Merge strategy: static ALL_ZONES provides display fields (name, platform, siteUrl);
// backend zone overrides metrics (reach, vi, ctr, cpm) if IDs match.
export function getSelectedZones(selectedIds = [], allZones = null, recoZones = null) {
  const dynamicPool = [...(recoZones || []), ...(allZones || [])]
  return selectedIds.map(id => {
    const dynamic = dynamicPool.find(z => z.id === id)  // backend zone (matching ID)
    const staticZ  = ALL_ZONES.find(z => z.id === id)   // static zone (dot-notation ID)
    if (staticZ && dynamic) return { ...staticZ, ...dynamic }   // static fields + dynamic metrics
    if (dynamic) return {                                        // backend only — derive display fields
      ...dynamic,
      name:     dynamic.name     || dynamic.id.replace(/_/g, ' '),
      platform: dynamic.platform || dynamic.channel || dynamic.id.split('_')[0],
    }
    return staticZ   // static-only fallback
  }).filter(Boolean)
}

// ─── Format VND ───────────────────────────────────────────────────────────────
export function fmtVnd(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(0) + 'k'
  return String(n)
}

// ─── Format impressions ───────────────────────────────────────────────────────
export function fmtImp(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

// ─── Estimated impressions for a zone given budget in triệu VND ───────────────
export function estImpressions(zone, budgetM) {
  if (!budgetM || !zone.cpm) return 0
  return Math.round((budgetM * 1_000_000) / zone.cpm * 1000)
}
