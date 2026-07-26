const express = require('express');
const router = express.Router();
const ZoneCatalog = require('../models/Zone');
const { withPublicSiteUrl } = require('../lib/siteUrls');

// GET /api/zones — return entire zone catalog (groups, channels, placements)
router.get('/', async (_req, res) => {
  try {
    const catalog = await ZoneCatalog.findOne({});
    if (!catalog) return res.json({ groups: [], channels: {}, placements: [] });
    res.json({
      groups:     catalog.groups,
      channels:   catalog.channels,
      placements: catalog.placements.map((placement) => withPublicSiteUrl(placement)),
      catalogVersion: catalog.catalogVersion || 'legacy-35',
      taxonomyVersion: catalog.taxonomyVersion || null,
      revision: catalog.revision || 1,
      previousVersion: catalog.previousVersion || null,
      creativeContracts: catalog.creativeContracts || [],
      topicTaxonomy: catalog.topicTaxonomy || [],
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/zones/placements — flat list only
router.get('/placements', async (req, res) => {
  try {
    const catalog = await ZoneCatalog.findOne({});
    if (!catalog) return res.json([]);
    const filters = {
      topicId: req.query.topic,
      publisher: req.query.publisher,
      placementFamily: req.query.family,
      device: req.query.device,
    };
    const placements = (catalog.placements || [])
      .map((placement) => withPublicSiteUrl(placement))
      .filter((placement) => Object.entries(filters).every(([field, value]) => {
        if (!value) return true;
        if (Array.isArray(placement[field])) return placement[field].includes(value);
        return placement[field] === value;
      }));
    res.json(placements);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/zones/placements/:id — single placement
router.get('/placements/:id', async (req, res) => {
  try {
    const catalog = await ZoneCatalog.findOne({});
    if (!catalog) return res.status(404).json({ error: 'Zone catalog not initialized' });
    const placement = catalog.placements.find((p) => p.id === req.params.id);
    if (!placement) return res.status(404).json({ error: `Placement "${req.params.id}" not found` });
    res.json(withPublicSiteUrl(placement));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
