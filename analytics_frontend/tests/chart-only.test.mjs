import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const tabShells = [
  'daily-ops.js',
  'awareness.js',
  'consideration.js',
  'conversion.js',
  'retention.js',
  'executive.js'
];

test('analytics tab shells contain charts without analytical narration', async () => {
  const sources = await Promise.all(
    tabShells.map(file =>
      readFile(new URL(`../tabs/${file}`, import.meta.url), 'utf8')
    )
  );
  const combined = sources.join('\n');

  for (const forbidden of [
    'card-usecase',
    'card-rule',
    'card-insight',
    'When to use:',
    'Decision rule:',
    'ex-recommendations',
    'Smart Recommendations'
  ]) {
    assert.doesNotMatch(combined, new RegExp(forbidden, 'i'));
  }

  assert.match(combined, /<canvas\b/);
});

test('daily operations charts do not generate trend or comparison conclusions', async () => {
  const source = await readFile(
    new URL('../tabs/daily-ops.js', import.meta.url),
    'utf8'
  );

  for (const forbidden of [
    'CTR improving',
    'CTR declining',
    'CTR stable around',
    'leads with the highest CTR',
    'Comparing <b>'
  ]) {
    assert.doesNotMatch(source, new RegExp(forbidden, 'i'));
  }
});

test('KPI scorecards render raw values without qualitative verdict text', async () => {
  const scorecards = [
    '../tabs/daily-ops.js',
    '../tabs/awareness/scorecard.js',
    '../tabs/consideration/scorecard.js',
    '../tabs/conversion/scorecard.js',
    '../tabs/retention/scorecard.js',
    '../tabs/executive/scorecard.js'
  ];
  const sources = await Promise.all(
    scorecards.map(file => readFile(new URL(file, import.meta.url), 'utf8'))
  );

  for (const source of sources) {
    assert.doesNotMatch(source, /<div class="sc-delta/);
  }
});
