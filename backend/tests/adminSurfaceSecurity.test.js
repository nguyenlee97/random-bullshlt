const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const adminRouter = require('../routes/admin');

test('public admin router exposes stats only and no destructive database operations', () => {
  const routes = adminRouter.stack
    .filter((layer) => layer.route)
    .flatMap((layer) => Object.keys(layer.route.methods).map((method) => ({
      method: method.toUpperCase(),
      path: layer.route.path,
    })));

  assert.deepEqual(routes, [{ method: 'GET', path: '/stats' }]);
});

test('AdsPilot production UI does not publish reset controls or API documentation', () => {
  const frontendRoot = path.join(__dirname, '..', '..', 'adspilot_frontend');
  const sources = [
    'api.js',
    'app.js',
    'index.html',
    path.join('views', 'console.js'),
  ].map((file) => fs.readFileSync(path.join(frontendRoot, file), 'utf8')).join('\n');

  assert.doesNotMatch(sources, /admin\/reset|reseed-zones|resetDb|confirmReset/);
  assert.doesNotMatch(sources, /Quick Test Endpoints|renderDocs|views\/docs\.js|data-nav="docs"/);
  assert.equal(fs.existsSync(path.join(frontendRoot, 'views', 'docs.js')), false);
  assert.match(sources, /production console is read-only/i);
});
