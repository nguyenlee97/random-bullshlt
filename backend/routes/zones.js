const express = require('express');
const router = express.Router();
const ZoneCatalog = require('../models/Zone');

// GET /api/zones — return entire zone catalog (groups, channels, placements)
router.get('/', async (_req, res) => {
  try {
    const catalog = await ZoneCatalog.findOne({});
    if (!catalog) return res.json({ groups: [], channels: {}, placements: [] });
    res.json({
      groups:     catalog.groups,
      channels:   catalog.channels,
      placements: catalog.placements,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/zones/placements — flat list only
router.get('/placements', async (_req, res) => {
  try {
    const catalog = await ZoneCatalog.findOne({});
    if (!catalog) return res.json([]);
    res.json(catalog.placements || []);
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
    res.json(placement);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
