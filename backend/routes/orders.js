const express = require('express');
const router = express.Router();
const Campaign = require('../models/Campaign');
const ZoneCatalog = require('../models/Zone');
const { validatePlacements } = require('../middleware/zoneValidator');
const { launchReportGeneration } = require('../services/reportLauncher');

// ── helpers ───────────────────────────────────────────────────────────────────
function nextOrderId(seq) {
  const yr = new Date().getFullYear();
  return `ORD-${yr}-${String(seq).padStart(3, '0')}`;
}

async function getSeq() {
  // createdAt is not a sequence: seed rows may share a timestamp, and two
  // concurrent requests can read the same "latest" row. Establish the current
  // year's maximum once, then advance it atomically in MongoDB.
  const year = new Date().getFullYear();
  const prefix = `ORD-${year}-`;
  const existing = await Campaign.find(
    { orderId: { $regex: `^${prefix}` } },
    { orderId: 1 }
  ).lean();
  const baseline = existing.reduce((highest, item) => {
    const match = String(item.orderId || '').match(/(\d+)$/);
    return match ? Math.max(highest, parseInt(match[1], 10)) : highest;
  }, 0);

  const result = await Campaign.db.collection('counters').findOneAndUpdate(
    { _id: `campaign_order_${year}` },
    [{
      $set: {
        seq: {
          $add: [
            {
              $cond: [
                { $gt: [{ $ifNull: ['$seq', 0] }, baseline] },
                { $ifNull: ['$seq', 0] },
                baseline,
              ],
            },
            1,
          ],
        },
      },
    }],
    { upsert: true, returnDocument: 'after' }
  );
  const counter = result && (result.value || result);
  if (!counter || !Number.isInteger(counter.seq)) {
    throw new Error('Could not allocate an order sequence');
  }
  return counter.seq;
}

async function getPlacementSnapshot(placementIds = []) {
  const catalog = await ZoneCatalog.findOne({}).lean();
  if (!catalog) return { catalogVersion: null, placements: [], catalogPlacements: [] };
  const selected = new Set(placementIds);
  const snapshots = (catalog.placements || [])
    .filter((placement) => selected.has(placement.id))
    .map((placement) => ({
      id: placement.id,
      publisher: placement.publisher || null,
      channel: placement.channel,
      format: placement.format,
      size: placement.size,
      topicId: placement.topicId || null,
      placementFamily: placement.placementFamily || null,
      comparisonGroupId: placement.comparisonGroupId || null,
      creativeContractId: placement.creativeContractId || null,
      metricSource: placement.metricSource || null,
      reach: placement.reach,
      vi: placement.vi,
      ctr: placement.ctr,
      cpm: placement.cpm,
      siteUrl: placement.siteUrl || null,
      catalogVersion: placement.catalogVersion || catalog.catalogVersion || null,
    }));
  return {
    catalogVersion: catalog.catalogVersion || 'legacy-35',
    placements: snapshots,
    catalogPlacements: catalog.placements || [],
  };
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
    deletedAt: null,  // exclude soft-deleted campaigns from conflict checks
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
    catalogVersion: doc.catalogVersion || null,
    placementSnapshots: doc.placementSnapshots || [],
    targeting:  doc.targeting,
    dmp:        doc.dmp,
    idempotencyKey: doc.idempotencyKey,
    warnings:   doc.warnings || [],
    createdAt:  doc.createdAt,
    updatedAt:  doc.updatedAt,
  };
}


async function ensureOrderReports(order) {
  try {
    await launchReportGeneration({
      campaignId: order.orderId,
      brand: order.brand,
      objective: order.objective,
      budget: order.budget,
      startDate: order.startDate,
      zones: order.placements || [],
      audience: [],
    });
  } catch (reportError) {
    // The order is already committed. Reporting can be retried idempotently
    // from the Report tab or Zalo without falsifying launch success.
    console.warn(`[orders] Report generation did not start for ${order.orderId}: ${reportError.message}`);
  }
}

// ── GET /api/orders ───────────────────────────────────────────────────────────
// Query params: ?status=active&brand=Nike
router.get('/', async (req, res) => {
  try {
    const filter = { deletedAt: null };  // exclude soft-deleted orders
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
    const order = await Campaign.findOne({ orderId: req.params.id, deletedAt: null }).lean();
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

    // ── Idempotency (Phase 0) ────────────────────────────────────────────────
    // If this key was already used, return the existing order instead of
    // creating a duplicate (agent retry after commit-then-timeout case).
    if (payload.idempotencyKey) {
      const existing = await Campaign.findOne({
        idempotencyKey: payload.idempotencyKey,
        deletedAt: null,
      }).lean();
      if (existing) {
        await ensureOrderReports(existing);
        return res.status(200).json({ ...formatOrder(existing), deduplicated: true });
      }
    }

    const seq = await getSeq();
    const snapshot = await getPlacementSnapshot(payload.placements || []);
    const placements = snapshot.catalogPlacements;

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
      catalogVersion: snapshot.catalogVersion,
      placementSnapshots: snapshot.placements,
      targeting:  payload.targeting  || {},
      dmp:        payload.dmp        || { include: [], exclude: [] },
      idempotencyKey: payload.idempotencyKey || undefined,
      warnings,
    });

    // Acquire the idempotent report-generation lease at the campaign commit
    // boundary. The Report tab remains a retry/polling client, not a dependency.
    await ensureOrderReports(order);

    res.status(201).json(formatOrder(order.toObject()));
  } catch (err) {
    // Race on idempotencyKey unique index (two concurrent retries): treat the
    // loser as a dedup hit and return the winner's order.
    if (err.code === 11000 && err.keyPattern && err.keyPattern.idempotencyKey) {
      const winner = await Campaign.findOne({
        idempotencyKey: req.body.idempotencyKey,
      }).lean();
      if (winner) {
        await ensureOrderReports(winner);
        return res.status(200).json({ ...formatOrder(winner), deduplicated: true });
      }
    }
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
    const targetPlacements = patch.placements  || order.placements;
    const snapshot = await getPlacementSnapshot(targetPlacements);
    const placements = snapshot.catalogPlacements;
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
    if (patch.placements !== undefined) {
      order.catalogVersion = snapshot.catalogVersion;
      order.placementSnapshots = snapshot.placements;
    }
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
// Soft delete: sets deletedAt timestamp. Document is retained so the orderId
// is never reused and analytic_records / report_analyses refs stay valid.
router.delete('/:id', async (req, res) => {
  try {
    const order = await Campaign.findOne({ orderId: req.params.id, deletedAt: null });
    if (!order) return res.status(404).json({ error: `Order "${req.params.id}" not found` });
    order.deletedAt = new Date();
    await order.save();
    res.json({ ok: true, deleted: req.params.id, deletedAt: order.deletedAt });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
