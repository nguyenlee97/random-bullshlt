const express = require('express');
const router = express.Router();
const AnalyticsRecord = require('../models/AnalyticsRecord');

// ── GET /api/analytics/data ───────────────────────────────────────────────────
// Query params: campaignId, placementId, startDate (YYYY-MM-DD), endDate
router.get('/data', async (req, res) => {
  try {
    const filter = {};
    if (req.query.campaignId)  filter.campaignId  = req.query.campaignId;
    if (req.query.placementId) filter.placementId = req.query.placementId;
    if (req.query.channel)     filter.channel     = req.query.channel;
    if (req.query.format)      filter.format      = req.query.format;
    if (req.query.startDate || req.query.endDate) {
      filter.date = {};
      if (req.query.startDate) filter.date.$gte = req.query.startDate;
      if (req.query.endDate)   filter.date.$lte = req.query.endDate;
    }

    const records = await AnalyticsRecord.find(filter).sort({ date: -1 }).lean();
    res.json(records);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/analytics/summary ────────────────────────────────────────────────
// Aggregated KPIs — optionally filtered by campaignId, date range
router.get('/summary', async (req, res) => {
  try {
    const match = {};
    if (req.query.campaignId) match.campaignId = req.query.campaignId;
    if (req.query.startDate || req.query.endDate) {
      match.date = {};
      if (req.query.startDate) match.date.$gte = req.query.startDate;
      if (req.query.endDate)   match.date.$lte = req.query.endDate;
    }

    const agg = await AnalyticsRecord.aggregate([
      { $match: match },
      {
        $group: {
          _id: null,
          totalImpressions: { $sum: '$impressions' },
          totalClicks:      { $sum: '$clicks' },
          totalSpend:       { $sum: '$spend' },
          totalConversions: { $sum: '$conversions' },
          totalReach:       { $sum: '$reach' },
          avgCTR:           { $avg: '$ctr' },
          avgCPM:           { $avg: '$cpm' },
          avgVI:            { $avg: '$vi' },
          recordCount:      { $sum: 1 },
        },
      },
    ]);

    const summary = agg[0] || {
      totalImpressions: 0, totalClicks: 0, totalSpend: 0,
      totalConversions: 0, totalReach: 0, avgCTR: 0, avgCPM: 0, avgVI: 0, recordCount: 0,
    };
    delete summary._id;

    res.json(summary);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/analytics/by-campaign ───────────────────────────────────────────
// Aggregated per campaign — for the overview table
router.get('/by-campaign', async (req, res) => {
  try {
    const match = {};
    if (req.query.startDate || req.query.endDate) {
      match.date = {};
      if (req.query.startDate) match.date.$gte = req.query.startDate;
      if (req.query.endDate)   match.date.$lte = req.query.endDate;
    }

    const rows = await AnalyticsRecord.aggregate([
      { $match: match },
      {
        $group: {
          _id:              '$campaignId',
          impressions:      { $sum: '$impressions' },
          clicks:           { $sum: '$clicks' },
          spend:            { $sum: '$spend' },
          conversions:      { $sum: '$conversions' },
          avgCTR:           { $avg: '$ctr' },
          avgCPM:           { $avg: '$cpm' },
        },
      },
      { $sort: { impressions: -1 } },
    ]);

    res.json(rows.map((r) => ({ campaignId: r._id, ...r, _id: undefined })));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/analytics/by-date ────────────────────────────────────────────────
// Daily trend — total impressions/clicks/spend per day
router.get('/by-date', async (req, res) => {
  try {
    const match = {};
    if (req.query.campaignId) match.campaignId = req.query.campaignId;
    if (req.query.startDate || req.query.endDate) {
      match.date = {};
      if (req.query.startDate) match.date.$gte = req.query.startDate;
      if (req.query.endDate)   match.date.$lte = req.query.endDate;
    }

    const rows = await AnalyticsRecord.aggregate([
      { $match: match },
      {
        $group: {
          _id:         '$date',
          impressions: { $sum: '$impressions' },
          clicks:      { $sum: '$clicks' },
          spend:       { $sum: '$spend' },
          conversions: { $sum: '$conversions' },
        },
      },
      { $sort: { _id: 1 } },
    ]);

    res.json(rows.map((r) => ({ date: r._id, ...r, _id: undefined })));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/analytics/by-placement ──────────────────────────────────────────
router.get('/by-placement', async (req, res) => {
  try {
    const match = {};
    if (req.query.campaignId) match.campaignId = req.query.campaignId;
    if (req.query.startDate || req.query.endDate) {
      match.date = {};
      if (req.query.startDate) match.date.$gte = req.query.startDate;
      if (req.query.endDate)   match.date.$lte = req.query.endDate;
    }

    const rows = await AnalyticsRecord.aggregate([
      { $match: match },
      {
        $group: {
          _id:         '$placementId',
          channel:     { $first: '$channel' },
          format:      { $first: '$format' },
          impressions: { $sum: '$impressions' },
          clicks:      { $sum: '$clicks' },
          spend:       { $sum: '$spend' },
          avgCTR:      { $avg: '$ctr' },
          avgVI:       { $avg: '$vi' },
        },
      },
      { $sort: { impressions: -1 } },
    ]);

    res.json(rows.map((r) => ({ placementId: r._id, ...r, _id: undefined })));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
