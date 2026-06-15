import { ALL_ZONES } from '@/data/zones'

// ─── Ratio mismatch check ─────────────────────────────────────────────────────
// Returns a warning string if aspect ratio differs >15%, null if OK
export function checkMismatch(zone, file) {
  if (!file?.width || !file?.height) return null
  const sizeStr = zone.size || ''
  const [zw, zh] = sizeStr.split('×').map(Number)
  if (!zw || !zh) return null
  const zRatio = zw / zh
  const fRatio = file.width / file.height
  if (Math.abs(zRatio - fRatio) / zRatio > 0.15) {
    const zLabel = zw > zh ? 'ngang' : 'dọc'
    const fLabel = file.width > file.height ? 'ngang' : 'dọc'
    return `Zone ${zone.size} (${zLabel}) · Ảnh ${file.width}×${file.height}px (${fLabel})`
  }
  return null
}

// ─── Smart score: how well a file fits a zone ─────────────────────────────────
export function scoreFile(file, zone) {
  let score = 0
  const fname = (file.name || '').toLowerCase()
  const platform = (zone.platform || '').toLowerCase()
  const placement = (zone.placement || zone.id?.split('_').slice(1).join(' ') || '').toLowerCase()
  const format = (zone.format || '').toLowerCase()

  if (platform && fname.includes(platform.slice(0, 4))) score += 3
  if (placement && fname.includes(placement)) score += 3
  if (format && fname.includes(format)) score += 2
  if (zone.size) {
    if (fname.includes(zone.size.replace('×', 'x'))) score += 5
    if (fname.includes(zone.size.replace('×', '_'))) score += 5
  }

  if (file.width && file.height && zone.size) {
    const [zw, zh] = zone.size.split('×').map(Number)
    if (zw && zh) {
      const diff = Math.abs((zw / zh) - (file.width / file.height)) / (zw / zh)
      if (diff < 0.02) score += 8
      else if (diff < 0.08) score += 4
      else if (diff < 0.15) score += 1
      else score -= 4
    }
  }
  return score
}

// ─── Get selectedZones array from IDs ─────────────────────────────────────────
// Accepts optional allZones array (e.g., real API zones) — falls back to static ALL_ZONES
export function getSelectedZones(selectedIds = [], allZones = null) {
  const catalog = allZones?.length ? allZones : ALL_ZONES
  return catalog.filter(z => selectedIds.includes(z.id))
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
