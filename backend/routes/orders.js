const express = require('express');
const router = express.Router();
const Campaign = require('../models/Campaign');
const ZoneCatalog = require('../models/Zone');
const { validatePlacements } = require('../middleware/zoneValidator');

// ── helpers ───────────────────────────────────────────────────────────────────
function nextOrderId(seq) {
  const yr = new Date().getFullYear();
  return `ORD-${yr}-${String(seq).padStart(3, '0')}`;
}

async function getSeq() {
  // Use the highest existing orderId numeric part + 1
  const last = await Campaign.findOne({}, { orderId: 1 })
    .sort({ createdAt: -1 })
    .lean();
  if (!last) return 4; // seed has 3 orders
  const match = last.orderId.match(/(\d+)$/);
  return match ? parseInt(match[1], 10) + 1 : 4;
}

async function getZonePlacements() {
  const catalog = await ZoneCatalog.findOne({}).lean();
  return catalog ? catalog.placements || [] : [];
}

/**
 * Check if any other active/pending campaign overlaps in zone AND date with this order.
 * Returns array of warning strings.
 */
async function checkZoneConflicts(placements, startDate, endDate, excludeOrderId) {
  if (!placements || !placements.length) return [];

  const query = {
    status: { $in: ['active', 'pending'] },
    placements: { $in: placements },
  };
  if (excludeOrderId) query.orderId = { $ne: excludeOrderId };

  const conflicts = await Campaign.find(query).select('orderId brand placements startDate endDate').lean();

  const warnings = [];
  for (const c of conflicts) {
    // Date overlap check: both must have dates to compare; no dates = always-on = always overlaps
    const hasNewDates = startDate && endDate;
    const hasExistDates = c.startDate && c.endDate;
    const overlaps = !hasNewDates || !hasExistDates
      || (c.startDate <= endDate && c.endDate >= startDate);

    if (!overlaps) continue;

    const sharedZones = placements.filter(p => c.placements.includes(p));
    if (sharedZones.length) {
      warnings.push(
        `Zone conflict: ${sharedZones.join(', ')} already booked by ${c.orderId} (${c.brand}) ` +
        `[${c.startDate || 'always'} → ${c.endDate || 'always'}]`
      );
    }
  }
  return warnings;
}

// Reformat mongoose doc → clean API shape matching mock
function formatOrder(doc) {
  return {
    id:         doc.orderId,
    brand:      doc.brand,
    advertiser: doc.advertiser,
    objective:  doc.objective,
    status:     doc.status,
    budget:     doc.budget,
    daily:      doc.daily,
    rate:       doc.rate,
    rateType:   doc.rateType,
    startDate:  doc.startDate,
    endDate:    doc.endDate,
    creative:   doc.creative,
    creatives:  doc.creatives || [],
    placements: doc.placements,
    targeting:  doc.targeting,
    dmp:        doc.dmp,
    warnings:   doc.warnings || [],
    createdAt:  doc.createdAt,
    updatedAt:  doc.updatedAt,
  };
}

// ── GET /api/orders ───────────────────────────────────────────────────────────
// Query params: ?status=active&brand=Nike
router.get('/', async (req, res) => {
  try {
    const filter = {};
    if (req.query.status) filter.status = req.query.status;
    if (req.query.brand)  filter.brand  = new RegExp(req.query.brand, 'i');

    const orders = await Campaign.find(filter).sort({ createdAt: -1 }).lean();
    res.json(orders.map(formatOrder));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/orders/:id ───────────────────────────────────────────────────────
router.get('/:id', async (req, res) => {
  try {
    const order = await Campaign.findOne({ orderId: req.params.id }).lean();
    if (!order) return res.status(404).json({ error: `Order "${req.params.id}" not found` });
    res.json(formatOrder(order));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/orders ──────────────────────────────────────────────────────────
router.post('/', async (req, res) => {
  try {
    const payload = req.body || {};
    const seq = await getSeq();
    const placements = await getZonePlacements();

    const sizeWarnings = validatePlacements(
      payload.placements || [],
      payload.creative   || {},
      placements,
      payload.creatives  || []
    );

    // Hard-block: zone conflict returns 409
    const conflicts = await checkZoneConflicts(
      payload.placements || [],
      payload.startDate  || '',
      payload.endDate    || '',
      null
    );
    if (conflicts.length) {
      return res.status(409).json({
        error: 'Zone conflict — one or more placements are already booked by another campaign in this date range.',
        conflicts,
      });
    }

    const warnings = sizeWarnings;

    const order = await Campaign.create({
      orderId:    nextOrderId(seq),
      brand:      payload.brand      || 'Untitled Brand',
      advertiser: payload.advertiser || payload.brand || '',
      objective:  payload.objective  || 'awareness',
      status:     payload.status     || 'pending',
      budget:     payload.budget     || 0,
      daily:      payload.daily      || 0,
      rate:       payload.rate       || 0,
      rateType:   payload.rateType   || 'CPM',
      startDate:  payload.startDate  || '',
      endDate:    payload.endDate    || '',
      creative:   payload.creative   || { name: '', size: '', url: '' },
      creatives:  payload.creatives  || [],
      placements: payload.placements || [],
      targeting:  payload.targeting  || {},
      dmp:        payload.dmp        || { include: [], exclude: [] },
      warnings,
    });

    res.status(201).json(formatOrder(order.toObject()));
  } catch (err) {
    if (err.name === 'ValidationError') return res.status(400).json({ error: err.message });
    res.status(500).json({ error: err.message });
  }
});

// ── PUT /api/orders/:id ───────────────────────────────────────────────────────
router.put('/:id', async (req, res) => {
  try {
    const patch = req.body || {};

    const order = await Campaign.findOne({ orderId: req.params.id });
    if (!order) return res.status(404).json({ error: `Order "${req.params.id}" not found` });

    // Re-validate zone compatibility if placements or creative changed
    const placements = await getZonePlacements();
    const targetPlacements = patch.placements  || order.placements;
    const targetCreative   = patch.creative    || order.creative;
    const targetStart      = patch.startDate   !== undefined ? patch.startDate : order.startDate;
    const targetEnd        = patch.endDate     !== undefined ? patch.endDate   : order.endDate;

    const sizeWarnings = validatePlacements(
      targetPlacements,
      targetCreative,
      placements,
      patch.creatives || order.creatives || []
    );

    // Hard-block: zone conflict returns 409
    const conflicts = await checkZoneConflicts(targetPlacements, targetStart, targetEnd, req.params.id);
    if (conflicts.length) {
      return res.status(409).json({
        error: 'Zone conflict — one or more placements are already booked by another campaign in this date range.',
        conflicts,
      });
    }

    const warnings = sizeWarnings;

    // Apply patch fields (whitelist important ones, spread rest)
    const allowed = ['brand','advertiser','objective','status','budget','daily','rate','rateType',
                     'startDate','endDate','creative','creatives','placements','targeting','dmp'];
    allowed.forEach((k) => { if (patch[k] !== undefined) order[k] = patch[k]; });
    order.warnings = warnings;

    await order.save();
    res.json(formatOrder(order.toObject()));
  } catch (err) {
    if (err.name === 'ValidationError') return res.status(400).json({ error: err.message });
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/orders/:id/pause ────────────────────────────────────────────────
router.post('/:id/pause', async (req, res) => {
  try {
    const order = await Campaign.findOne({ orderId: req.params.id });
    if (!order) return res.status(404).json({ error: `Order "${req.params.id}" not found` });
    order.status = 'paused';
    await order.save();
    res.json({ ok: true, id: order.orderId, newStatus: 'paused' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/orders/:id/resume ───────────────────────────────────────────────
router.post('/:id/resume', async (req, res) => {
  try {
    const order = await Campaign.findOne({ orderId: req.params.id });
    if (!order) return res.status(404).json({ error: `Order "${req.params.id}" not found` });
    order.status = 'active';
    await order.save();
    res.json({ ok: true, id: order.orderId, newStatus: 'active' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/orders/:id/archive ─────────────────────────────────────────────
router.post('/:id/archive', async (req, res) => {
  try {
    const order = await Campaign.findOne({ orderId: req.params.id });
    if (!order) return res.status(404).json({ error: `Order "${req.params.id}" not found` });
    order.status = 'archived';
    await order.save();
    res.json({ ok: true, id: order.orderId, newStatus: 'archived' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── DELETE /api/orders/:id ────────────────────────────────────────────────────
router.delete('/:id', async (req, res) => {
  try {
    const result = await Campaign.deleteOne({ orderId: req.params.id });
    if (result.deletedCount === 0)
      return res.status(404).json({ error: `Order "${req.params.id}" not found` });
    res.json({ ok: true, deleted: req.params.id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
