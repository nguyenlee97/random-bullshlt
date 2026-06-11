const express = require('express');
const router = express.Router();
const Campaign        = require('../models/Campaign');
const AnalyticsRecord = require('../models/AnalyticsRecord');
const EventLog        = require('../models/EventLog');
const ApiLog          = require('../models/ApiLog');
const AudienceLibrary = require('../models/AudienceLibrary');

// POST /api/admin/reset
// Wipes runtime data (campaigns, analytics, events, api logs).
// NOTE: Zones catalog is preserved. Re-seeding is done via `npm run seed` (Block 5).
router.post('/reset', async (_req, res) => {
  try {
    await Promise.all([
      Campaign.deleteMany({}),
      AnalyticsRecord.deleteMany({}),
      EventLog.deleteMany({}),
      ApiLog.deleteMany({}),
    ]);
    res.json({ ok: true, message: 'Runtime data cleared. Run `npm run seed` to restore seed data.' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/admin/stats — quick DB stats
router.get('/stats', async (_req, res) => {
  try {
    const [campaigns, analytics, events, apiLogs, audienceLibrary] = await Promise.all([
      Campaign.countDocuments(),
      AnalyticsRecord.countDocuments(),
      EventLog.countDocuments(),
      ApiLog.countDocuments(),
      AudienceLibrary.countDocuments(),
    ]);
    res.json({ campaigns, analytics, events, apiLogs, audienceLibrary });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
