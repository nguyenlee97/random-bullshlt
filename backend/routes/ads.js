const express = require('express');
const router = express.Router();
const ZoneCatalog = require('../models/Zone');
const Campaign    = require('../models/Campaign');
const EventLog    = require('../models/EventLog');

// ── GET /api/ads/check?zone=<zoneId>&site=<siteId> ───────────────────────────
// Called by test site api.js to fetch the active ad for a given zone.
// Returns the best-matching active campaign's creative, or null if none.
router.get('/check', async (req, res) => {
  try {
    const { zone, site } = req.query;
    if (!zone) return res.status(400).json({ error: 'zone query param required' });

    // Find active campaigns that include this placement, within their flight dates.
    // Dates are stored as YYYY-MM-DD strings in Vietnam local time (UTC+7).
    // Server runs UTC, so we offset +7h when computing today.
    const nowVN  = new Date(Date.now() + 7 * 60 * 60 * 1000); // shift to UTC+7
    const today  = nowVN.toISOString().slice(0, 10);           // "YYYY-MM-DD"

    const campaigns = await Campaign.find({
      status: 'active',
      placements: zone,
      $or: [
        { startDate: { $in: ['', null] } },                     // always-on (no date)
        {
          $and: [
            { $or: [{ startDate: '' }, { startDate: { $lte: today } }] },
            { $or: [{ endDate: '' },   { endDate:   { $gte: today } }] },
          ]
        },
      ],
    }).lean();

    if (!campaigns.length) {
      return res.json({ ad: null, zone, site: site || null });
    }

    // Simple selection: pick the first active campaign (could be improved with pacing)
    const campaign = campaigns[0];

    // ── Smart creative selection: zone-specific → size-match → format-match ──
    // 1. Zone-specific: creative.zones[] explicitly lists this zone ID (highest priority)
    // 2. Size-match: creative.size matches the zone's required size
    // 3. Format-match: creative.format matches (e.g. "skin")
    // 4. First creative in array as last resort
    let matchedCreative = null;
    try {
      const catalog = await ZoneCatalog.findOne().lean();
      const placement = (catalog?.placements || []).find(p => p.id === zone);
      if (campaign.creatives && campaign.creatives.length) {
        // Priority 1: zone-specific match
        matchedCreative = campaign.creatives.find(
          c => Array.isArray(c.zones) && c.zones.includes(zone)
        );
        // Priority 2+: size / format / first
        if (!matchedCreative && placement) {
          matchedCreative = campaign.creatives.find(c => c.size === placement.size)
                         || campaign.creatives.find(c => c.format === placement.format)
                         || campaign.creatives[0];
        }
      }
    } catch (_) { /* catalog lookup failure — fall through to legacy */ }

    // Fall back to legacy single creative field
    const creative = (matchedCreative && matchedCreative.url)
      ? matchedCreative
      : campaign.creative;

    res.json({
      ad: {
        campaignId:  campaign.orderId,
        placementId: zone,
        brand:       campaign.brand,
        creative,
        clickUrl:    creative?.url || '',
      },
      zone,
      site: site || null,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});


// ── POST /api/ads/impression ──────────────────────────────────────────────────
// Body: { campaignId, placementId, siteId }
router.post('/impression', async (req, res) => {
  try {
    const { campaignId, placementId, siteId } = req.body || {};
    if (!campaignId || !placementId)
      return res.status(400).json({ error: 'campaignId and placementId required' });

    await EventLog.create({
      type:        'impression',
      campaignId,
      placementId,
      siteId:      siteId || '',
      ip:          req.ip,
      userAgent:   req.headers['user-agent'] || '',
      referrer:    req.headers['referer']    || '',
    });

    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/ads/click ───────────────────────────────────────────────────────
// Body: { campaignId, placementId, siteId }
router.post('/click', async (req, res) => {
  try {
    const { campaignId, placementId, siteId } = req.body || {};
    if (!campaignId || !placementId)
      return res.status(400).json({ error: 'campaignId and placementId required' });

    await EventLog.create({
      type:        'click',
      campaignId,
      placementId,
      siteId:      siteId || '',
      ip:          req.ip,
      userAgent:   req.headers['user-agent'] || '',
      referrer:    req.headers['referer']    || '',
    });

    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
