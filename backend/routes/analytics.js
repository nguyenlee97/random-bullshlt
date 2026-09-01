const express = require('express');
const router = express.Router();
const AnalyticsRecord = require('../models/AnalyticsRecord');
const CampaignReportState = require('../models/CampaignReportState');
const { activeSnapshot } = require('../services/reportDatasets');

async function recordsFor(filters = {}) {
  const query = filters.campaignId ? { campaignId: filters.campaignId } : {};
  const states = await CampaignReportState.find({ ...query, activeRevision: { $gt: 1 } }).lean();
  const snapshots = await Promise.all(states.map(s => activeSnapshot(s.campaignId)));
  const active = snapshots.filter(s => s?.analyses?.length === 6);
  const ids = active.map(s => s.campaignId);
  const legacy = await AnalyticsRecord.find({ ...query, ...(ids.length ? { campaignId: { $nin: ids, ...(filters.campaignId ? { $eq: filters.campaignId } : {}) } } : {}) }).lean();
  const records = legacy.concat(active.flatMap(s => s.records));
  return records.filter(row => ['placementId', 'channel', 'format'].every(k => !filters[k] || row[k] === filters[k]) &&
    (!filters.startDate || row.date >= filters.startDate) && (!filters.endDate || row.date <= filters.endDate));
}

function summarize(records) {
  const sum = key => records.reduce((total, row) => total + Number(row[key] || 0), 0);
  return {
    totalImpressions: sum('impressions'), totalClicks: sum('clicks'), totalSpend: sum('spend'),
    totalConversions: sum('conversions'), totalReach: sum('reach'),
    avgCTR: records.length ? sum('ctr') / records.length : 0,
    avgCPM: records.length ? sum('cpm') / records.length : 0,
    avgVI: records.length ? sum('vi') / records.length : 0, recordCount: records.length,
  };
}

router.get('/data', async (req, res) => {
  try { res.set('Cache-Control', 'no-store'); res.json((await recordsFor(req.query)).sort((a, b) => b.date.localeCompare(a.date))); }
  catch (error) { res.status(500).json({ error: error.message }); }
});
router.get('/summary', async (req, res) => {
  try { res.set('Cache-Control', 'no-store'); res.json(summarize(await recordsFor(req.query))); }
  catch (error) { res.status(500).json({ error: error.message }); }
});
for (const [path, key] of [['by-campaign', 'campaignId'], ['by-date', 'date'], ['by-placement', 'placementId']]) {
  router.get('/' + path, async (req, res) => {
    try {
      const grouped = new Map();
      for (const row of await recordsFor(req.query)) {
        if (!grouped.has(row[key])) grouped.set(row[key], []);
        grouped.get(row[key]).push(row);
      }
      const values = [...grouped].map(([id, rows]) => {
        const s = summarize(rows);
        return { [key]: id, impressions: s.totalImpressions, clicks: s.totalClicks,
          spend: s.totalSpend, conversions: s.totalConversions, avgCTR: s.avgCTR, avgCPM: s.avgCPM,
          ...(key === 'placementId' ? { channel: rows[0].channel, format: rows[0].format, avgVI: s.avgVI } : {}) };
      });
      values.sort(key === 'date' ? (a, b) => a.date.localeCompare(b.date) : (a, b) => b.impressions - a.impressions);
      res.set('Cache-Control', 'no-store'); res.json(values);
    } catch (error) { res.status(500).json({ error: error.message }); }
  });
}
module.exports = router;
