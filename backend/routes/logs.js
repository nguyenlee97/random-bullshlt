const express = require('express');
const router = express.Router();
const ApiLog = require('../models/ApiLog');

// GET /api/logs — last N API log entries
// Query: ?limit=100&method=POST
router.get('/', async (req, res) => {
  try {
    const limit  = Math.min(parseInt(req.query.limit, 10) || 100, 500);
    const filter = {};
    if (req.query.method) filter.method = req.query.method.toUpperCase();
    if (req.query.path)   filter.path   = new RegExp(req.query.path, 'i');

    const logs = await ApiLog.find(filter)
      .sort({ ts: -1 })
      .limit(limit)
      .lean();

    res.json(logs);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/logs — clear all API logs
router.delete('/', async (_req, res) => {
  try {
    await ApiLog.deleteMany({});
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
