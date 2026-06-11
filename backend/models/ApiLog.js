const mongoose = require('mongoose');

// API call log — mirrors the localStorage log from the mock
const apiLogSchema = new mongoose.Schema(
  {
    method:  { type: String, required: true },   // GET | POST | PUT | DELETE
    path:    { type: String, required: true },
    query:   { type: mongoose.Schema.Types.Mixed, default: null },
    body:    { type: mongoose.Schema.Types.Mixed, default: null },
    status:  { type: Number, default: 200 },
    resBody: { type: mongoose.Schema.Types.Mixed, default: null },
    ip:      { type: String, default: '' },
    ts:      { type: Date, default: Date.now, index: true },
  },
  {
    collection: 'api_logs',
    timestamps: false,
  }
);

// Keep only 1000 most recent (TTL index not ideal; will prune in logger middleware)
module.exports = mongoose.model('ApiLog', apiLogSchema);
