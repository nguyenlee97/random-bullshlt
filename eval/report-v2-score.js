#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const fixture = {
  campaignId: 'VOLTRIDE-EVAL',
  brand: 'VoltRide',
  objective: 'conversion',
  budget: 450_000_000,
  startDate: '2026-08-20',
  endDate: '2026-09-23',
  kpi: [
    'Tối thiểu 3.000 lượt đăng ký lái thử đủ điều kiện.',
    'CPL đăng ký lái thử không vượt quá 150.000 VND.',
    'Tỷ lệ khách đến lái thử đạt tối thiểu 70%.',
    'Tối thiểu 525 khách đặt cọc trong vòng 14 ngày sau khi lái thử.',
    'Chi phí trên mỗi lượt đặt cọc không vượt quá 900.000 VND.',
  ].join(' '),
  notes: 'CTA duy nhất: Đăng ký lái thử. Theo dõi đăng ký, khách đủ điều kiện, đến lái thử, đặt cọc và mua xe.',
  zones: [
    { id: 'zalo_news_native', channel: 'Zalo', format: 'native', cpm: 48_000 },
    { id: 'zalo_inbox_banner', channel: 'Zalo', format: 'banner', cpm: 55_000 },
  ],
  forecast: { estimatedImpressions: 8_700_000, estimatedReach: 2_700_000, averageCpm: 51_000, frequency: 3.2 },
};

const safeRequire = relative => {
  try { return require(path.join(root, relative)); } catch (_) { return {}; }
};

const measurement = safeRequire('backend/lib/reportMeasurement');
const simulator = safeRequire('backend/lib/reportSyntheticData');
const contractLib = safeRequire('backend/lib/reportContract');
const generator = safeRequire('backend/services/reportGenerator');

let score = 0;
let input;
let spec;
let rows;
let contract;

try {
  input = measurement.normalizeReportInput?.(fixture);
  spec = measurement.buildMeasurementSpec?.(input || fixture);
  const ids = new Set(spec?.outcomeGraph?.events?.map(event => event.id));
  if (spec?.version === 'measurement-spec-v2'
      && ['test_ride_registration', 'qualified_test_ride', 'attended_test_ride', 'deposit', 'purchase'].every(id => ids.has(id))) score += 10;

  const ecommerce = measurement.buildMeasurementSpec?.(measurement.normalizeReportInput?.({
    ...fixture,
    campaignId: 'SHOP-EVAL', brand: 'Shop', kpi: 'Tối thiểu 1.000 đơn hàng. CPA đơn hàng không quá 120.000 VND.',
    notes: 'Theo dõi checkout và purchase.',
  }));
  const ecommerceIds = new Set(ecommerce?.outcomeGraph?.events?.map(event => event.id));
  if (ecommerceIds.has('purchase') && !ecommerceIds.has('deposit')) score += 10;

  if (input?.durationDays === 35 && input?.endDate === fixture.endDate && input?.inputHash) score += 10;

  rows = simulator.simulateReportFacts?.(input, spec);
  const rowsAgain = simulator.simulateReportFacts?.(input, spec);
  if (Array.isArray(rows) && JSON.stringify(rows) === JSON.stringify(rowsAgain)) score += 10;

  if (rows?.length === 70 && new Set(rows.map(row => row.date)).size === 35) score += 10;

  const spend = rows?.reduce((sum, row) => sum + row.spend, 0) || 0;
  const valid = rows?.every(row => {
    const formulaCtr = row.impressions ? row.clicks / row.impressions * 100 : 0;
    const chain = spec.outcomeGraph.events.map(event => Number(row.outcomes?.[event.id] || 0));
    return Math.abs(formulaCtr - row.ctr) < 0.002
      && chain.every((value, index) => index === 0 || value <= chain[index - 1]);
  });
  if (valid && spend > 0 && spend <= fixture.budget) score += 10;

  contract = contractLib.buildReportContract?.(input, rows, spec);
  if (contract?.contractVersion === 'report-evidence-v2'
      && contract?.findings?.some(item => item.id === 'business_funnel')
      && contract?.findings?.some(item => item.id === 'kpi_scorecard')) score += 10;

  const statuses = new Set(contract?.kpiScorecard?.map(item => item.status));
  if (contract?.performanceStatus && statuses.size >= 2) score += 10;

  if (contract?.actions?.length >= 2 && contract.actions.every(action => (
    action.problem && action.evidenceIds?.length && action.proposedAction
    && action.guardrail && action.nextReviewWindow
  ))) score += 10;

  const questions = generator.questionsForReport?.('conversion', contract) || [];
  const ui = fs.readFileSync(path.join(root, 'agent_frontend/src/steps/ReportStep.jsx'), 'utf8');
  if (questions.some(item => /lái thử|đặt cọc|qualified|funnel/i.test(item.question))
      && /Tổng quan/.test(ui) && /performanceStatus|kpiScorecard/.test(ui)) score += 10;
} catch (_) {
  // A partial implementation earns only checks completed before the failure.
}

process.stdout.write(String(score));
