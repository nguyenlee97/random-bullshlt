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

    // Find active campaigns that include this placement
    const campaigns = await Campaign.find({
      status: 'active',
      placements: zone,
    }).lean();

    if (!campaigns.length) {
      return res.json({ ad: null, zone, site: site || null });
    }

    // Simple selection: pick the first active campaign (could be improved with pacing)
    const campaign = campaigns[0];

    res.json({
      ad: {
        campaignId:  campaign.orderId,
        placementId: zone,
        brand:       campaign.brand,
        creative:    campaign.creative,
        clickUrl:    campaign.creative?.url || '',
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
