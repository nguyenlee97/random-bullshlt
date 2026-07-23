import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const api = readFileSync(new URL('../src/api/agentApi.js', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const selector = readFileSync(new URL('../src/components/ExperienceSelector.jsx', import.meta.url), 'utf8')
const workspace = readFileSync(new URL('../src/components/WorkspacePane/index.jsx', import.meta.url), 'utf8')
const workFoot = readFileSync(new URL('../src/components/WorkspacePane/WorkFoot.jsx', import.meta.url), 'utf8')

test('new campaigns send one explicit immutable conversational model', () => {
  assert.match(api, /conversation_model: conversationModel/)
  assert.match(api, /conversation-models/)
  assert.match(app, /newChat\(\{[\s\S]*conversationModel/)
  assert.match(app, /context\.conversation_model \|\| 'greennode_minimax'/)
})

test('homepage shows both model choices and disables unavailable engines', () => {
  assert.match(selector, /conversation-model-selector/)
  assert.match(selector, /OpenAI · GPT-5\.4 mini/)
  assert.match(selector, /GreenNode · MiniMax M2\.5/)
  assert.match(selector, /disabled=\{!model\.available \|\| busy\}/)
  assert.match(selector, /onSelect\(mode\.id, selectedModel\)/)
})

test('resume displays the stored model but exposes no mid-run switch', () => {
  assert.match(selector, /modelLabel\(item\.conversation_model\)/)
  assert.doesNotMatch(api, /updateConversationModel|setConversationModel/)
})

test('workspace keeps model routing internal after the homepage choice', () => {
  assert.doesNotMatch(workspace, /conversationModel=\{conversationModel\}/)
  assert.doesNotMatch(workFoot, /OpenAI|GPT-5|GreenNode|MiniMax|conversationModel/)
  assert.match(workFoot, /Current workflow tool/)
})
