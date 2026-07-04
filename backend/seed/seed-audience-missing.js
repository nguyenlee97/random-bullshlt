/**
 * Incremental audience seed — inserts ONLY segments missing from the DB.
 *
 * Why not `node seed/index.js --force`: a full re-seed drops and recreates docs,
 * which changes every `_id`. Existing campaigns' dmp.include references and the
 * eval golden-set labels are keyed on current _ids — they must survive. ⛔
 *
 * This script upserts on segmentId (unique index): the existing 71 docs are
 * left untouched (same _id); the ~239 sheet rows not yet in MongoDB are inserted.
 *
 * Run (locally against the live DB, or on the VPS):
 *   cd backend
 *   MONGODB_URI="mongodb://<user>:<pass>@api.pawgrammers.io.vn:27017/adspilot?authSource=admin" node seed/seed-audience-missing.js
 * On the VPS the default localhost URI works:  node seed/seed-audience-missing.js
 */
const path = require('path');
const xlsx = require('xlsx');
const mongoose = require('mongoose');
const AudienceLibrary = require('../models/AudienceLibrary');

const AUDIENCE_FILE = path.join(__dirname, 'data', 'Audience Library.xlsx');
const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/adspilot';

function readAudienceFromExcel() {
  const wb = xlsx.readFile(AUDIENCE_FILE);
  const rows = xlsx.utils.sheet_to_json(wb.Sheets['Sheet1'], { defval: null });
  return rows
    .filter((r) => r['ID'] && r['Name'])
    .map((r) => ({
      segmentId:   r['ID'],
      type:        r['Type'],
      category:    r['Category']    || '',
      subcategory: r['Subcategory'] || null,
      name:        r['Name'],
      context:     r['Context']     || null,
      fullLabel:   r['Full Label']  || r['Name'],
      sizeMin:     r['Size Min']    || null,
      sizeMax:     r['Size Max']    || null,
      sizeRaw:     r['Size (raw)']  || null,
    }));
}

(async () => {
  await mongoose.connect(URI);
  console.log(`connected: ${URI.replace(/\/\/.*@/, '//***@')}`);

  const sheet = readAudienceFromExcel();
  const existing = new Set(
    (await AudienceLibrary.find({}, { segmentId: 1 }).lean()).map((d) => d.segmentId)
  );
  const missing = sheet.filter((s) => !existing.has(s.segmentId));

  console.log(`sheet: ${sheet.length} | in DB: ${existing.size} | missing: ${missing.length}`);
  if (missing.length) {
    const res = await AudienceLibrary.insertMany(missing, { ordered: false });
    console.log(`✅ inserted ${res.length} new segments (existing docs & _ids untouched)`);
  } else {
    console.log('nothing to do');
  }

  const total = await AudienceLibrary.countDocuments();
  console.log(`total now: ${total}`);
  await mongoose.disconnect();
})().catch((e) => { console.error(e); process.exit(1); });
