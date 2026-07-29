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

function repairSourceIdentity(file, format) {
  const filename = normalizeHint(file.name)
  const formatHint = normalizeHint(format.format_id)
  const sizeHint = normalizeHint(`${format.width}x${format.height}`)
  if (file.formatId === format.format_id) return 3
  if (formatHint && filename.includes(formatHint)) return 2
  if (sizeHint && filename.includes(sizeHint)) return 1
  return 0
}

export function rankRepairSourceFiles(files = [], format = {}) {
  const targetWidth = Number(format.width || 0)
  const targetHeight = Number(format.height || 0)
  const targetRatio = targetWidth / Math.max(targetHeight, 1)
  return files
    .map((file, index) => {
      const width = Number(file.width || file.deterministic?.width || 0)
      const height = Number(file.height || file.deterministic?.height || 0)
      const ratio = width / Math.max(height, 1)
      const ratioDiff = width && height
        ? Math.abs(ratio - targetRatio)
        : Number.POSITIVE_INFINITY
      const resolutionDiff = width && height && targetWidth && targetHeight
        ? Math.abs(width - targetWidth) / targetWidth
          + Math.abs(height - targetHeight) / targetHeight
        : Number.POSITIVE_INFINITY
      return {
        file,
        index,
        identity: repairSourceIdentity(file, format),
        ratioDiff,
        resolutionDiff,
      }
    })
    .sort((left, right) => (
      right.identity - left.identity
      || left.ratioDiff - right.ratioDiff
      || left.resolutionDiff - right.resolutionDiff
      || left.index - right.index
    ))
    .map(item => item.file)
}

export function selectRepairSourceFile(files = [], format = {}) {
  return rankRepairSourceFiles(files, format)[0]
}

export function matchPlannedFormat(file, item) {
  const targetWidth = Number(item.width || 0)
  const targetHeight = Number(item.height || 0)
  const fileWidth = Number(file.width || file.deterministic?.width || 0)
  const fileHeight = Number(file.height || file.deterministic?.height || 0)
  const filename = normalizeHint(file.name)
  const formatHint = normalizeHint(item.format_id)
  const sizeHint = normalizeHint(`${targetWidth}x${targetHeight}`)
  const canonicalIdentity = file.formatId === item.format_id
    || Boolean(formatHint && filename.includes(formatHint))
  const weakSizeHint = Boolean(sizeHint && filename.includes(sizeHint))
  const isSkin = item.intended_format === 'skin'
  const skinHint = inferIntendedFormat(file) === 'skin'
    || filename.includes('skin')
    || filename.includes('background')
    || file.formatId === item.format_id

  if (canonicalIdentity) {
    if (!fileWidth || !fileHeight || !targetWidth || !targetHeight) {
      return { matched: true, label: 'khớp tên/format chuẩn', identityMatch: true }
    }
    const targetRatio = targetWidth / targetHeight
    const ratioDiff = Math.abs(targetRatio - (fileWidth / fileHeight)) / targetRatio
    return {
      matched: true,
      label: ratioDiff < MAX_AUTOPILOT_RATIO_DIFF
        ? 'khớp tên/format chuẩn'
        : `khớp tên/format chuẩn · tỷ lệ lệch ${(ratioDiff * 100).toFixed(0)}%`,
      identityMatch: true,
      ratioDiff,
      ratioAdvisory: ratioDiff >= MAX_AUTOPILOT_RATIO_DIFF,
    }
  }
  if (isSkin && !skinHint) return { matched: false, label: 'chọn Skin / Background' }
  if (!fileWidth || !fileHeight || !targetWidth || !targetHeight) {
    return weakSizeHint || (isSkin && skinHint)
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
