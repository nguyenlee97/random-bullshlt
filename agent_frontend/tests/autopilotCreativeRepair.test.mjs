import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..', '..')

async function source(relativePath) {
  return readFile(path.join(root, relativePath), 'utf8')
}

test('Autopilot creative repair persists an already reviewed file set', async () => {
  const app = await source('agent_frontend/src/App.jsx')
  const chat = await source('agent_frontend/src/hooks/useChat.js')

  assert.match(
    app,
    /persistReadyCreative:\s*editingStep === 2/,
    'the Autopilot editor must request persistence for creative repairs',
  )
  assert.match(
    chat,
    /if \(persistReadyCreative\) \{[\s\S]*?AgentAPI\.approveCreative\(stepData\.creative\)[\s\S]*?responseAllowsAdvance\(response\)/,
    'ready creative files must be committed and validated before leaving the editor',
  )
})
