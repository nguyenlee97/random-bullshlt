const SKIN_FORMAT_IDS = new Set(['zuma-Left', 'zuma-Right', 'znews-Background'])

export const MAX_AUTOPILOT_RATIO_DIFF = 0.15

export function inferIntendedFormat(file) {
  if (file.intendedFormat) return file.intendedFormat
  if (SKIN_FORMAT_IDS.has(file.formatId)) return 'skin'
  if (file.type?.startsWith('video/')) return 'video'
  return 'banner'
}

const normalizeHint = value => String(value || '')
  .toLowerCase()
  .replace('×', 'x')
  .replace(/[^a-z0-9]+/g, '')

export function matchPlannedFormat(file, item) {
  const targetWidth = Number(item.width || 0)
  const targetHeight = Number(item.height || 0)
  const fileWidth = Number(file.width || file.deterministic?.width || 0)
  const fileHeight = Number(file.height || file.deterministic?.height || 0)
  const filename = normalizeHint(file.name)
  const formatHint = normalizeHint(item.format_id)
  const sizeHint = normalizeHint(`${targetWidth}x${targetHeight}`)
  const explicitHint = file.formatId === item.format_id
    || (formatHint && filename.includes(formatHint))
    || (sizeHint && filename.includes(sizeHint))
  const isSkin = item.intended_format === 'skin'
  const skinHint = inferIntendedFormat(file) === 'skin'
    || filename.includes('skin')
    || filename.includes('background')
    || file.formatId === item.format_id

  if (isSkin && !skinHint) return { matched: false, label: 'chọn Skin / Background' }
  if (!fileWidth || !fileHeight || !targetWidth || !targetHeight) {
    return explicitHint || (isSkin && skinHint)
      ? { matched: true, label: 'khớp theo tên/format' }
      : { matched: false, label: 'chưa đủ thông tin' }
  }
  if (fileWidth === targetWidth && fileHeight === targetHeight) {
    return { matched: true, label: 'đúng kích thước' }
  }
  const targetRatio = targetWidth / targetHeight
  const ratioDiff = Math.abs(targetRatio - (fileWidth / fileHeight)) / targetRatio
  if (ratioDiff < MAX_AUTOPILOT_RATIO_DIFF) {
    return {
      matched: true,
      label: `đúng tỷ lệ · lệch ${(ratioDiff * 100).toFixed(1)}%`,
      ratioDiff,
    }
  }
  return {
    matched: false,
    label: `sai tỷ lệ · lệch ${(ratioDiff * 100).toFixed(0)}%`,
    ratioDiff,
  }
}
