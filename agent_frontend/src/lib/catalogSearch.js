export function foldCatalogText(value) {
  return String(value ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .replace(/[×✕]/g, 'x')
    .toLowerCase()
    .trim()
}

export function matchesCatalogSearch(values, query) {
  const needle = foldCatalogText(query)
  if (!needle) return true
  return foldCatalogText(
    (Array.isArray(values) ? values : [values]).filter(Boolean).join(' '),
  ).includes(needle)
}
