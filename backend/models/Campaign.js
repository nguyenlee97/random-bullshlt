const mongoose = require('mongoose');

// ── Creative sub-schema ───────────────────────────────────────────────────────
const creativeSchema = new mongoose.Schema(
  {
    name: { type: String, default: '' },
    size: { type: String, default: '' },  // e.g. "720x1280"
    url:  { type: String, default: '' },
  },
  { _id: false }
);

// ── Targeting sub-schema ──────────────────────────────────────────────────────
const targetingSchema = new mongoose.Schema(
  {
    geo:       [{ type: String }],
    age:       [{ type: String }],
    gender:    [{ type: String }],
    deviceOS:  [{ type: String }],
    deviceBrand: [{ type: String }],
    marital:   [{ type: String }],
    parental:  [{ type: String }],
    education: [{ type: String }],
    income:    [{ type: String }],
    career:    [{ type: String }],
    interest:  [{ type: String }],
    weather:   [{ type: String }],
  },
  { _id: false }
);

// ── DMP sub-schema ────────────────────────────────────────────────────────────
const dmpSchema = new mongoose.Schema(
  {
    include: [{ type: String }],
    exclude: [{ type: String }],
  },
  { _id: false }
);

// ── Campaign / Order ──────────────────────────────────────────────────────────
const campaignSchema = new mongoose.Schema(
  {
    // Human-readable sequential ID: ORD-2026-001
    orderId:    { type: String, required: true, unique: true, index: true },
    brand:      { type: String, required: true },
    advertiser: { type: String, default: '' },
    objective:  { type: String, enum: ['awareness', 'consideration', 'conversion', 'retention'], default: 'awareness' },
    status:     { type: String, enum: ['pending', 'active', 'paused', 'draft', 'archived'], default: 'pending', index: true },

    budget:   { type: Number, default: 0 },       // lifetime limit (impressions or VND)
    daily:    { type: Number, default: 0 },       // daily limit
    rate:     { type: Number, default: 0 },       // price per unit (CPM/CPC/CPV/FlatFee)
    rateType: { type: String, enum: ['CPM', 'CPC', 'CPV', 'FlatFee'], default: 'CPM' },

    startDate: { type: String, default: '' },     // ISO date string YYYY-MM-DD
    endDate:   { type: String, default: '' },

    creative:   { type: creativeSchema,   default: () => ({}) },
    placements: [{ type: String }],               // placement IDs from zone catalog
    targeting:  { type: targetingSchema,  default: () => ({}) },
    dmp:        { type: dmpSchema,        default: () => ({ include: [], exclude: [] }) },

    // Zone validation warnings (populated at create/update time)
    warnings:   [{ type: String }],
  },
  {
    collection: 'campaigns',
    timestamps: { createdAt: 'createdAt', updatedAt: 'updatedAt' },
  }
);

module.exports = mongoose.model('Campaign', campaignSchema);
