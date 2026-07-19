export function normalizeDmpAttr(raw = {}) {
  const code = String(
    raw.segmentId || raw.code || raw.segment_code || raw._uid || raw._id || '',
  )
  const name = raw.fullLabel || raw.name || raw.label || '(unknown)'
  const sizeMin = Number(raw.sizeMin ?? 0)
  const sizeMax = Number(raw.sizeMax ?? 0)
  const estSize = sizeMin && sizeMax
    ? Math.round((sizeMin + sizeMax) / 2)
    : Number(raw.est_size || sizeMin || sizeMax || 0)

  return {
    ...raw,
    _uid: code || name,
    code,
    name,
    type: (raw.type || raw.segment_type || '').toLowerCase(),
    category: raw.category || raw.segment_category || '',
    est_size: estSize,
    sizeMin,
    sizeMax,
    sizeRaw: raw.sizeRaw || null,
  }
}

export function dedupeDmpAttrs(attrs = []) {
  const seen = new Set()
  const unique = []
  for (const raw of attrs) {
    const attr = normalizeDmpAttr(raw)
    const identity = String(attr._uid || attr.name || '').trim().toLowerCase()
    if (!identity || seen.has(identity)) continue
    seen.add(identity)
    unique.push(attr)
  }
  return unique
}

// Union model: selecting more segments increases reach while discounting overlap.
export function calcAudienceSize(attrs = []) {
  if (!attrs.length) return 0
  const knownSizes = attrs.map(a => Number(a.est_size || 0)).filter(size => size > 0)
  if (!knownSizes.length) return 0
  knownSizes.sort((a, b) => b - a)
  return Math.round(knownSizes.reduce(
    (total, size, index) => total + size * Math.pow(0.7, index),
    0,
  ))
}

export function normalizeAudienceSelection(value = {}, fallback = {}) {
  const sourceAttrs = Array.isArray(value.attrs)
    ? value.attrs
    : (Array.isArray(fallback.attrs) ? fallback.attrs : [])
  const attrs = dedupeDmpAttrs(sourceAttrs)
  const explicitSize = Number(value.size || value.estimated_size || 0)

  return {
    ...fallback,
    ...value,
    attrs,
    size: explicitSize > 0 ? explicitSize : calcAudienceSize(attrs),
  }
}

export function enrichAudienceSelection(value = {}, catalog = []) {
  const catalogByUid = new Map(
    catalog.map(normalizeDmpAttr).map(attr => [attr._uid, attr]),
  )
  const attrs = dedupeDmpAttrs((value.attrs || []).map(raw => {
    const selected = normalizeDmpAttr(raw)
    const catalogAttr = catalogByUid.get(selected._uid)
    if (!catalogAttr) return selected
    return normalizeDmpAttr({
      ...catalogAttr,
      ...selected,
      est_size: selected.est_size || catalogAttr.est_size,
      sizeMin: selected.sizeMin || catalogAttr.sizeMin,
      sizeMax: selected.sizeMax || catalogAttr.sizeMax,
    })
  }))

  return {
    ...value,
    attrs,
    size: Number(value.size || 0) || calcAudienceSize(attrs),
  }
}
