const mongoose = require('mongoose');

// API call log — mirrors the localStorage log from the mock
const apiLogSchema = new mongoose.Schema(
  {
    method:  { type: String, required: true },   // GET | POST | PUT | DELETE
    requestId: { type: String, default: '', index: true },
    path:    { type: String, required: true },
    query:   { type: mongoose.Schema.Types.Mixed, default: null },
    body:    { type: mongoose.Schema.Types.Mixed, default: null },
    status:  { type: Number, default: 200 },
    resBody: { type: mongoose.Schema.Types.Mixed, default: null },
    ip:      { type: String, default: '' },
    ts:      { type: Date, default: Date.now },
  },
  {
    collection: 'api_logs',
    timestamps: false,
  }
);

// Operational request logs are diagnostic data, not business records.
apiLogSchema.index({ ts: 1 }, { expireAfterSeconds: 30 * 24 * 60 * 60 });

// Keep only 1000 most recent (TTL index not ideal; will prune in logger middleware)
module.exports = mongoose.model('ApiLog', apiLogSchema);
