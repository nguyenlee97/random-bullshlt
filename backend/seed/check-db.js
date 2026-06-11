/**
 * Block 5 pre-flight: checks MongoDB is reachable before seeding.
 * Run: node seed/check-db.js
 */
require('dotenv').config();
const mongoose = require('mongoose');

const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/adspilot';

async function main() {
  console.log(`\n🔍  Checking MongoDB at: ${URI}\n`);

  try {
    await mongoose.connect(URI, { serverSelectionTimeoutMS: 5000 });

    const admin  = mongoose.connection.db.admin();
    const status = await admin.serverStatus();
    const dbs    = await admin.listDatabases();

    console.log('✅  Connected successfully');
    console.log(`    Host    : ${mongoose.connection.host}:${mongoose.connection.port}`);
    console.log(`    DB name : ${mongoose.connection.name}`);
    console.log(`    Version : MongoDB ${status.version}`);
    console.log(`    Uptime  : ${Math.round(status.uptime / 60)} min`);
    console.log(`\n📦  Existing databases:`);
    dbs.databases.forEach((d) =>
      console.log(`    - ${d.name}  (${(d.sizeOnDisk / 1024).toFixed(1)} KB)`)
    );

    // Check if adspilot DB already has collections
    const colls = await mongoose.connection.db.listCollections().toArray();
    if (colls.length) {
      console.log(`\n⚠️   "adspilot" DB already has ${colls.length} collection(s):`);
      colls.forEach((c) => console.log(`    - ${c.name}`));
      console.log('\n    Run with --force to overwrite, or proceed to seeding.\n');
    } else {
      console.log('\n✨  "adspilot" DB is empty — ready for seeding.\n');
    }

    process.exit(0);
  } catch (err) {
    console.error(`\n❌  Connection FAILED: ${err.message}`);
    console.error('    Make sure mongod is running on the expected host/port.\n');
    process.exit(1);
  }
}

main();
