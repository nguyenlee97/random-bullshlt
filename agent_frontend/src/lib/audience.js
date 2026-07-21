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
    sizeSource: raw.sizeSource || null,
    sizeEstimateVersion: raw.sizeEstimateVersion || null,
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

export function hasKnownAudienceSize(attrs = []) {
  return attrs.some(raw => {
    const attr = normalizeDmpAttr(raw)
    return Number(attr.est_size || attr.sizeMin || attr.sizeMax || 0) > 0
  })
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
    size: explicitSize > 0 ? explicitSize : 0,
    sizeKnown: explicitSize > 0 && value.reach?.status !== 'unavailable',
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
      sizeSource: selected.sizeSource || catalogAttr.sizeSource,
      sizeEstimateVersion: selected.sizeEstimateVersion || catalogAttr.sizeEstimateVersion,
    })
  }))

  return {
    ...value,
    attrs,
    size: Number(value.size || 0),
    sizeKnown: Boolean(value.sizeKnown && Number(value.size || 0) > 0),
  }
}
