import assert from 'node:assert/strict'
import test from 'node:test'

import {
  hasSeenOpenAIWalkthroughTool,
  rememberOpenAIWalkthroughTool,
} from '../src/demo/walkthroughMessageTracker.js'

const injected = tool => ({ detail: { metadata: { tool } } })

test('OpenAI walkthrough remembers audience and setup messages that arrive before the waiter', () => {
  const seen = new Set()

  assert.equal(
    rememberOpenAIWalkthroughTool(seen, 'openai_gpt_5_4_mini', injected('audience_entry')),
    true,
  )
  assert.equal(
    rememberOpenAIWalkthroughTool(seen, 'openai_gpt_5_4_mini', injected('setup_entry')),
    true,
  )
  assert.equal(
    hasSeenOpenAIWalkthroughTool(seen, 'openai_gpt_5_4_mini', 'audience_entry'),
    true,
  )
  assert.equal(
    hasSeenOpenAIWalkthroughTool(seen, 'openai_gpt_5_4_mini', 'setup_entry'),
    true,
  )
})

test('GreenNode walkthrough does not use the OpenAI message history', () => {
  const seen = new Set()

  assert.equal(
    rememberOpenAIWalkthroughTool(seen, 'greennode_minimax', injected('audience_entry')),
    false,
  )
  assert.equal(
    hasSeenOpenAIWalkthroughTool(seen, 'greennode_minimax', 'audience_entry'),
    false,
  )
  assert.deepEqual([...seen], [])
})

test('OpenAI tracker ignores injected messages without tool metadata', () => {
  const seen = new Set()

  assert.equal(
    rememberOpenAIWalkthroughTool(seen, 'openai_gpt_5_4_mini', { detail: {} }),
    false,
  )
  assert.deepEqual([...seen], [])
})
