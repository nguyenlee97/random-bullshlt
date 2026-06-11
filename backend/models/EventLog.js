const mongoose = require('mongoose');

// Raw impression / click events from test sites
const eventLogSchema = new mongoose.Schema(
  {
    type:        { type: String, enum: ['impression', 'click'], required: true, index: true },
    campaignId:  { type: String, required: true, index: true },
    placementId: { type: String, required: true, index: true },
    siteId:      { type: String, default: '' },    // 'znews' | 'baomoi' | 'zingmp3'
    ip:          { type: String, default: '' },
    userAgent:   { type: String, default: '' },
    referrer:    { type: String, default: '' },
    timestamp:   { type: Date, default: Date.now, index: true },
  },
  {
    collection: 'event_logs',
    timestamps: false,
  }
);

module.exports = mongoose.model('EventLog', eventLogSchema);
