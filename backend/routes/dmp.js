const express = require('express');
const router = express.Router();
const AudienceLibrary = require('../models/AudienceLibrary');

// GET /api/dmp/attributes
// Returns all audience segments (Interest + Behavior) from MongoDB.
// Query params:
//   ?type=Interest|Behavior   — filter by type
//   ?category=<text>          — filter by category (case-insensitive)
//   ?q=<text>                 — search by name/fullLabel
//   ?limit=<n>                — default 500
router.get('/attributes', async (req, res) => {
  try {
    const filter = {};
    if (req.query.type)     filter.type     = req.query.type;
    if (req.query.category) filter.category = new RegExp(req.query.category, 'i');
    if (req.query.q) {
      filter.$or = [
        { name:      new RegExp(req.query.q, 'i') },
        { fullLabel: new RegExp(req.query.q, 'i') },
        { category:  new RegExp(req.query.q, 'i') },
      ];
    }

    const limit = Math.min(parseInt(req.query.limit, 10) || 500, 1000);
    const segments = await AudienceLibrary.find(filter)
      .sort({ type: 1, category: 1, name: 1 })
      .limit(limit)
      .lean();

    res.json(segments);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/dmp/attributes/categories
// Returns distinct categories grouped by type — useful for building the UI picker
router.get('/attributes/categories', async (req, res) => {
  try {
    const result = await AudienceLibrary.aggregate([
      {
        $group: {
          _id:   { type: '$type', category: '$category' },
          count: { $sum: 1 },
        },
      },
      { $sort: { '_id.type': 1, '_id.category': 1 } },
    ]);

    const grouped = {};
    for (const row of result) {
      const { type, category } = row._id;
      if (!grouped[type]) grouped[type] = [];
      grouped[type].push({ category, count: row.count });
    }

    res.json(grouped);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/dmp/attributes/:id — single segment by segmentId (e.g. INT001)
router.get('/attributes/:id', async (req, res) => {
  try {
    const seg = await AudienceLibrary.findOne({ segmentId: req.params.id }).lean();
    if (!seg) return res.status(404).json({ error: `Segment "${req.params.id}" not found` });
    res.json(seg);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
