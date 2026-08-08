#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });

const { normalizeReportInput, buildMeasurementSpec } = require('../lib/reportMeasurement');
const { simulateReportFacts } = require('../lib/reportSyntheticData');
const { buildReportContract } = require('../lib/reportContract');

async function main() {
  const args = process.argv.slice(2);
  const withModel = args.includes('--with-model');
  const fixtureArg = args.find(value => !value.startsWith('--'));
  const fixturePath = fixtureArg
    ? path.resolve(process.cwd(), fixtureArg)
    : path.resolve(__dirname, '..', 'tests', 'fixtures', 'voltride-report-v2.json');
  const raw = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
  const input = normalizeReportInput(raw);
  const measurementSpec = buildMeasurementSpec(input);
  const records = simulateReportFacts(input, measurementSpec);
  const dataContract = buildReportContract(input, records, measurementSpec);
  const output = {
    input: {
      campaignId: input.campaignId, brand: input.brand, objective: input.objective,
      startDate: input.startDate, endDate: input.endDate,
      durationDays: input.durationDays, inputHash: input.inputHash,
    },
    measurementSpec,
    records: { count: records.length, sample: records.slice(0, 2) },
    dataContract,
  };
  if (withModel) {
    const { generateAnalysis } = require('../services/reportGenerator');
    output.analyses = {};
    for (const reportType of ['daily_ops', input.objective]) {
      output.analyses[reportType] = await generateAnalysis(input, records, reportType);
    }
  }
  process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
}

main().catch(error => {
  process.stderr.write(`report preview failed: ${error.message}\n`);
  process.exitCode = 1;
});
