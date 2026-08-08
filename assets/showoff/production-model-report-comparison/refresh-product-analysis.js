'use strict';

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..', '..');
const { validateAnalysisResult } = require(path.join(ROOT, 'backend/lib/reportContract'));
const { questionsForReport, groundAnalysisResult } = require(path.join(ROOT, 'backend/services/reportGenerator'));

const dataPath = path.join(__dirname, 'report-data.json');
const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));

for (const report of data.reports) {
  const productAnalysis = groundAnalysisResult(structuredClone(report.model.rawAnalysis), report.contract);
  validateAnalysisResult(
    productAnalysis,
    questionsForReport(report.input.objective, report.contract),
    report.contract,
  );
  report.model.productAnalysis = productAnalysis;
}

fs.writeFileSync(dataPath, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
console.log(`Refreshed grounded product analysis in ${dataPath}`);
