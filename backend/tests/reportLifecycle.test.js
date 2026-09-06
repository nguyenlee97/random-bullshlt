'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function loadGenerateRouteWith(launchReportGeneration) {
  const launcherPath = require.resolve('../services/reportLauncher');
  const routePath = require.resolve('../routes/reports');
  const savedLauncher = require.cache[launcherPath];
  const savedRoute = require.cache[routePath];
  require.cache[launcherPath] = {
    id: launcherPath,
    filename: launcherPath,
    loaded: true,
    exports: { launchReportGeneration },
  };
  delete require.cache[routePath];
  const router = require('../routes/reports');
  const layer = router.stack.find(item => item.route?.path === '/generate');

  return {
    handler: layer.route.stack[0].handle,
    restore() {
      delete require.cache[routePath];
      if (savedRoute) require.cache[routePath] = savedRoute;
      if (savedLauncher) require.cache[launcherPath] = savedLauncher;
      else delete require.cache[launcherPath];
    },
  };
}

test('the generate route preserves the complete canonical campaign snapshot', async () => {
  let received;
  const loaded = loadGenerateRouteWith(async input => {
    received = input;
    return { status: 'generating', campaignId: input.campaignId };
  });
  try {
    let response;
    await loaded.handler({ body: {
      campaignId: 'ORD-2026-100', brand: 'VoltRide', objective: 'conversion',
      budget: 120_000_000, startDate: '2026-08-10', endDate: '2026-09-08',
      kpi: '300 đăng ký lái thử đủ điều kiện', notes: 'Tối ưu qualified test ride',
      zones: [{ id: 'znews_homepage_banner' }], targeting: { geo: ['HCM'] },
      forecast: { expectedLeads: 300 }, creative: { files: [{ id: 'creative-1' }] },
    } }, { json(value) { response = value; }, status() { return this; } });

    assert.equal(response.status, 'generating');
    assert.equal(received.endDate, '2026-09-08');
    assert.equal(received.kpi, '300 đăng ký lái thử đủ điều kiện');
    assert.deepEqual(received.targeting, { geo: ['HCM'] });
    assert.deepEqual(received.forecast, { expectedLeads: 300 });
    assert.deepEqual(received.creative, { files: [{ id: 'creative-1' }] });
  } finally {
    loaded.restore();
  }
});

test('report lifecycle keeps legacy analyses read-only by default', () => {
  const { inspectReportGeneration } = require('../services/reportLauncher');
  const legacy = [{ status: 'ready', dataContract: { contractVersion: 'report-evidence-v1' } }];
  assert.equal(inspectReportGeneration(legacy, 'new-input').action, 'preserve_legacy');
  assert.equal(inspectReportGeneration(legacy, 'new-input', true).action, 'start');
});

test('report lifecycle queues a newer input rather than dropping it', () => {
  const { inspectReportGeneration } = require('../services/reportLauncher');
  const generatorSource = require('node:fs').readFileSync(
    path.join(__dirname, '../services/reportGenerator.js'), 'utf8'
  );
  assert.equal(inspectReportGeneration([{ status: 'generating', inputHash: 'old' }], 'new').action, 'newer_input');
  assert.equal(inspectReportGeneration([{ status: 'generating', inputHash: 'same' }], 'same').action, 'same_generation');
  assert.match(generatorSource, /continueQueuedReportGeneration/);
  assert.match(generatorSource, /Continuing with queued input/);
});
