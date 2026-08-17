import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  ACTIVE_CAMPAIGN_ENGINE_ID,
  resolveActiveCampaignEngine,
} from '../src/lib/campaignEnginePolicy.js'

const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const selector = readFileSync(new URL('../src/components/ExperienceSelector.jsx', import.meta.url), 'utf8')
const workspace = readFileSync(new URL('../src/components/WorkspacePane/index.jsx', import.meta.url), 'utf8')
const workFoot = readFileSync(new URL('../src/components/WorkspacePane/WorkFoot.jsx', import.meta.url), 'utf8')
const landing = readFileSync(new URL('../src/components/PublicLanding.jsx', import.meta.url), 'utf8')
const techDocs = readFileSync(new URL('../public/tech-docs.html', import.meta.url), 'utf8')

test('new campaigns send the active engine explicitly while keeping the API contract', () => {
  assert.match(api, /conversation_model: conversationModel/)
  assert.match(api, /conversation-models/)
  assert.match(app, /conversationModel: activeCampaignEngine/)
  assert.match(app, /resolveActiveCampaignEngine\(conversationModelCatalog\)/)
  assert.match(app, /context\.conversation_model \|\| 'greennode_minimax'/)
})

test('active engine policy never falls back to the catalog default or another provider', () => {
  const catalog = {
    default_model: 'greennode_minimax',
    models: [
      { id: 'greennode_minimax', available: true },
      { id: ACTIVE_CAMPAIGN_ENGINE_ID, available: true },
    ],
  }
  assert.equal(resolveActiveCampaignEngine(catalog), ACTIVE_CAMPAIGN_ENGINE_ID)
  catalog.models[1].available = false
  assert.equal(resolveActiveCampaignEngine(catalog), '')
  assert.equal(resolveActiveCampaignEngine({ ...catalog, models: [catalog.models[0]] }), '')
})

test('homepage hides model choice and only exposes Copilot or Autopilot', () => {
  assert.doesNotMatch(selector, /conversation-model-selector|conversation-model/)
  assert.doesNotMatch(selector, /model\.label|model\.description|selectedModel/)
  assert.doesNotMatch(selector, /Model cho campaign|trạng thái model/)
  assert.match(selector, /campaignEngineReady/)
  assert.match(selector, /onSelect\(mode\.id\)/)
})

test('landing, direct entry, and both tours share the hidden engine policy', () => {
  assert.match(app, /startCampaign\([\s\S]*?demoMode === 'autopilot' \? 'autopilot' : 'guided',[\s\S]*?landingEntryAttempt/)
  assert.match(app, /startCampaign\(mode === 'autopilot' \? 'autopilot' : 'guided', attempt\)/)
  assert.doesNotMatch(app, /models\.find\(item => item\.available\)/)
  assert.doesNotMatch(app, /conversationModelCatalog\.default_model\s*\|\|/)
})

test('resume keeps the stored model internal and exposes no mid-run switch', () => {
  assert.doesNotMatch(selector, /modelLabel\(item\.conversation_model\)/)
  assert.doesNotMatch(selector, /item\.conversation_model/)
  assert.doesNotMatch(api, /updateConversationModel|setConversationModel/)
})

test('workspace keeps model routing internal after the homepage choice', () => {
  assert.doesNotMatch(workspace, /conversationModel=\{conversationModel\}/)
  assert.doesNotMatch(workFoot, /OpenAI|GPT-5|GreenNode|MiniMax|conversationModel/)
  assert.match(workFoot, /Current workflow tool/)
})

test('public customer surfaces contain no provider or named-model wording', () => {
  const publicCopy = [selector, landing, techDocs].join('\n')
  assert.doesNotMatch(publicCopy, /GreenNode|OpenAI|MiniMax|GPT/i)
})
