/**
 * Production-safe NP-6 catalog migration.
 *
 * Dry run:
 *   node seed/migrate-np6-catalog.js
 *
 * Apply:
 *   node seed/migrate-np6-catalog.js --apply --deployment-id=np6-2026-07-26.3
 *
 * The migration:
 * - validates the 35 legacy placement contracts before writing;
 * - snapshots the current catalog in zone_catalog_revisions;
 * - updates the existing catalog document in place;
 * - never changes campaigns, audience data, or analytics;
 * - is a no-op when the intended NP-6 catalog is already active.
 */
require('dotenv').config();

const crypto = require('crypto');
const mongoose = require('mongoose');

const ZoneCatalog = require('../models/Zone');
const {
  buildLegacyZonesCatalog,
  buildZonesCatalog,
  readZonesFromExcel,
} = require('./index');
const { NP6_CATALOG_VERSION } = require('./np6-catalog');
const EXPECTED_NP6_PLACEMENTS = 258;

const LEGACY_CONTRACT_FIELDS = [
  'id',
  'channel',
  'format',
  'size',
  'reach',
  'vi',
  'ctr',
  'cpm',
  'obj',
  'metricSource',
  'inventoryTier',
  'testSiteZone',
  'siteId',
  'siteUrl',
];

function deploymentIdFromArgs(argv = process.argv) {
  const value = argv.find((arg) => arg.startsWith('--deployment-id='));
  return value ? value.slice('--deployment-id='.length).trim() : '';
}

function comparablePlacement(placement) {
  return Object.fromEntries(
    LEGACY_CONTRACT_FIELDS.map((field) => [field, placement[field] ?? null])
  );
}

function stableCatalogHash(catalog) {
  // Hash the shape Mongoose actually persists. The source seed intentionally
  // contains legacy-only annotations such as mockId/notes that are not part of
  // the strict production schema and therefore must not make verification fail.
  const persisted = new ZoneCatalog(catalog).toObject({
    depopulate: true,
    versionKey: false,
  });
  const payload = {
    catalogVersion: persisted.catalogVersion,
    taxonomyVersion: persisted.taxonomyVersion,
    revision: persisted.revision,
    previousVersion: persisted.previousVersion,
    groups: persisted.groups,
    channels: persisted.channels,
    placements: persisted.placements,
    creativeContracts: persisted.creativeContracts,
    topicTaxonomy: persisted.topicTaxonomy,
  };
  return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
}

function validateLegacyContracts(currentCatalog, legacyCatalog) {
  const currentById = new Map(
    (currentCatalog.placements || []).map((placement) => [placement.id, placement])
  );
  const failures = [];

  for (const expected of legacyCatalog.placements) {
    const current = currentById.get(expected.id);
    if (!current) {
      failures.push(`${expected.id}: missing from production catalog`);
      continue;
    }
    const actualJson = JSON.stringify(comparablePlacement(current));
    const expectedJson = JSON.stringify(comparablePlacement(expected));
    if (actualJson !== expectedJson) {
      failures.push(`${expected.id}: legacy contract differs`);
    }
  }

  if (failures.length) {
    throw new Error(
      `Legacy placement validation failed (${failures.length}):\n- ${failures.join('\n- ')}`
    );
  }
}

async function migrateNp6Catalog({
  apply = process.argv.includes('--apply'),
  deploymentId = deploymentIdFromArgs(),
} = {}) {
  const mockRows = await readZonesFromExcel();
  const legacyCatalog = buildLegacyZonesCatalog(mockRows);
  const candidate = buildZonesCatalog(mockRows);
  const current = await ZoneCatalog.findOne().lean();

  if (!current) {
    throw new Error('Production catalog is missing; refusing to create it via migration');
  }
  if (legacyCatalog.placements.length !== 35) {
    throw new Error(`Expected 35 legacy placements, got ${legacyCatalog.placements.length}`);
  }
  if (candidate.placements.length !== EXPECTED_NP6_PLACEMENTS) {
    throw new Error(
      `Expected ${EXPECTED_NP6_PLACEMENTS} NP-6 placements, got ${candidate.placements.length}`
    );
  }

  validateLegacyContracts(current, legacyCatalog);

  const previousVersion = (
    current.catalogVersion === NP6_CATALOG_VERSION && current.previousVersion
  )
    ? current.previousVersion
    : (current.catalogVersion || 'legacy-35');
  const activationCandidate = {
    ...candidate,
    previousVersion,
  };
  const currentHash = stableCatalogHash(current);
  const candidateHash = stableCatalogHash(activationCandidate);
  const summary = {
    mode: apply ? 'apply' : 'dry-run',
    deploymentId: deploymentId || null,
    fromVersion: current.catalogVersion || 'legacy-35',
    toVersion: candidate.catalogVersion,
    fromPlacements: (current.placements || []).length,
    toPlacements: candidate.placements.length,
    currentHash,
    candidateHash,
  };

  if (
    current.catalogVersion === NP6_CATALOG_VERSION
    && (current.placements || []).length === candidate.placements.length
    && currentHash === candidateHash
  ) {
    console.log(JSON.stringify({ ...summary, status: 'already-current' }, null, 2));
    return { ...summary, status: 'already-current' };
  }

  if (!apply) {
    console.log(JSON.stringify({ ...summary, status: 'validated-dry-run' }, null, 2));
    return { ...summary, status: 'validated-dry-run' };
  }
  if (!deploymentId) {
    throw new Error('--deployment-id is required with --apply');
  }

  const revisions = mongoose.connection.collection('zone_catalog_revisions');
  await revisions.createIndex({ deploymentId: 1 }, { unique: true });
  await revisions.updateOne(
    { deploymentId },
    {
      $setOnInsert: {
        deploymentId,
        capturedAt: new Date(),
        sourceCatalogId: current._id,
        sourceVersion: current.catalogVersion || 'legacy-35',
        sourceHash: currentHash,
        catalog: current,
      },
    },
    { upsert: true }
  );

  const update = {
    groups: candidate.groups,
    channels: candidate.channels,
    placements: candidate.placements,
    catalogVersion: candidate.catalogVersion,
    taxonomyVersion: candidate.taxonomyVersion,
    revision: candidate.revision,
    previousVersion: activationCandidate.previousVersion,
    creativeContracts: candidate.creativeContracts,
    topicTaxonomy: candidate.topicTaxonomy,
  };
  await ZoneCatalog.updateOne({ _id: current._id }, { $set: update }, { runValidators: true });

  const activated = await ZoneCatalog.findById(current._id).lean();
  const activatedHash = stableCatalogHash(activated);
  if (
    activated.catalogVersion !== NP6_CATALOG_VERSION
    || activated.placements.length !== EXPECTED_NP6_PLACEMENTS
    || activatedHash !== candidateHash
  ) {
    throw new Error('Post-migration catalog verification failed');
  }

  const result = {
    ...summary,
    status: 'activated',
    activatedHash,
    snapshotCollection: 'zone_catalog_revisions',
  };
  console.log(JSON.stringify(result, null, 2));
  return result;
}

async function main() {
  const uri = process.env.MONGODB_URI || 'mongodb://localhost:27017/adspilot';
  await mongoose.connect(uri);
  try {
    await migrateNp6Catalog();
  } finally {
    await mongoose.disconnect();
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exit(1);
  });
}

module.exports = {
  LEGACY_CONTRACT_FIELDS,
  EXPECTED_NP6_PLACEMENTS,
  comparablePlacement,
  deploymentIdFromArgs,
  migrateNp6Catalog,
  stableCatalogHash,
  validateLegacyContracts,
};
