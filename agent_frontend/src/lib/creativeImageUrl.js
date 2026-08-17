export function creativeImageSource(source) {
  const value = String(source || '').trim()
  if (!value) return ''
  if (/^(data:|https?:|blob:|\/)/i.test(value)) return value
  return `data:image/png;base64,${value}`
}

export function creativeImageCrossOrigin(source) {
  return /^https?:/i.test(String(source || '').trim()) ? 'anonymous' : undefined
}

export function assignCreativeImageSource(image, source) {
  const resolved = creativeImageSource(source)
  const crossOrigin = creativeImageCrossOrigin(resolved)
  if (crossOrigin) image.crossOrigin = crossOrigin
  image.src = resolved
  return resolved
}
