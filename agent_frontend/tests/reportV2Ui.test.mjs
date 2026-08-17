import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = resolve(fileURLToPath(new URL('.', import.meta.url)))
const source = readFileSync(resolve(here, '../src/steps/ReportStep.jsx'), 'utf8')

test('Report v2 keeps all six generated report perspectives accessible', () => {
  for (const tab of ['daily_ops', 'awareness', 'consideration', 'conversion', 'retention', 'executive']) {
    assert.match(source, new RegExp(`id: '${tab}'`))
  }
  assert.match(source, /const visibleTabs = REPORT_TABS/)
  assert.match(source, /const objective = formState\?\.brief\?\.objective \|\| 'awareness'/)
  assert.match(source, /const isObjective = tab\.id === objective/)
})
