/**
 * Idempotently fill only audience rows whose imported catalog has no size.
 * Existing values and Mongo _ids are never replaced. Use --dry-run to inspect.
 */
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
const mongoose = require('mongoose');
const AudienceLibrary = require('../models/AudienceLibrary');
const { audienceSizeEstimate } = require('../lib/audienceSizeEstimate');

const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/adspilot';
const DRY_RUN = process.argv.includes('--dry-run');
const MISSING_SIZE = {
  $and: [
    { $or: [{ sizeMin: null }, { sizeMin: { $exists: false } }, { sizeMin: { $lte: 0 } }] },
    { $or: [{ sizeMax: null }, { sizeMax: { $exists: false } }, { sizeMax: { $lte: 0 } }] },
  ],
};

(async () => {
  await mongoose.connect(URI);
  const rows = await AudienceLibrary.find(MISSING_SIZE).lean();
  const operations = rows.map((row) => ({
    updateOne: {
      filter: { _id: row._id, ...MISSING_SIZE },
      update: {
        $set: {
          ...audienceSizeEstimate(row),
          sizeEstimatedAt: new Date(),
        },
      },
    },
  }));

  let modified = 0;
  if (!DRY_RUN && operations.length) {
    const result = await AudienceLibrary.bulkWrite(operations, { ordered: false });
    modified = result.modifiedCount;
  }
  console.log(JSON.stringify({
    dryRun: DRY_RUN,
    candidates: rows.length,
    modified,
    total: await AudienceLibrary.countDocuments(),
  }));
  await mongoose.disconnect();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
