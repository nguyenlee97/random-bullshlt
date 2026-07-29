export function campaignIdFromRecord(record) {
  return String(record?.campaignId || record?.['Campaign ID'] || '').trim();
}

export function requestedCampaignId(search = '') {
  const value = new URLSearchParams(search).get('campaignId');
  return String(value || '').trim();
}

export function campaignOptions(records = [], orders = [], requestedId = '') {
  const labels = new Map();

  for (const order of orders || []) {
    const id = String(order?.id || order?.orderId || '').trim();
    if (!id) continue;
    const brand = String(order?.brand || order?.advertiser || '').trim();
    labels.set(id, brand ? `${brand} · ${id}` : id);
  }

  for (const record of records || []) {
    const id = campaignIdFromRecord(record);
    if (id && !labels.has(id)) labels.set(id, id);
  }

  if (requestedId && !labels.has(requestedId)) labels.set(requestedId, requestedId);

  return [...labels.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => b.value.localeCompare(a.value, 'en', { numeric: true }));
}

export function filterRecords(records = [], filters = {}) {
  const campaignId = String(filters.brand || filters.campaignId || '').trim();
  const placementId = String(filters.zone || filters.placementId || '').trim();
  const channel = String(filters.audience || filters.channel || '').trim();
  const startDate = String(filters.startDate || '').trim();
  const endDate = String(filters.endDate || '').trim();

  return (records || []).filter(record => {
    const recordCampaignId = campaignIdFromRecord(record);
    const recordPlacementId = String(record?.placementId || record?.zone || record?.Zone || '').trim();
    const recordChannel = String(
      record?.audienceSegment ||
      record?.['Audience Segment'] ||
      record?.channel ||
      ''
    ).trim();
    const recordDate = String(record?.date || record?.Date || '').trim();

    if (campaignId && recordCampaignId !== campaignId) return false;
    if (placementId && recordPlacementId !== placementId) return false;
    if (channel && recordChannel !== channel) return false;
    if (startDate && recordDate < startDate) return false;
    if (endDate && recordDate > endDate) return false;
    return true;
  });
}
