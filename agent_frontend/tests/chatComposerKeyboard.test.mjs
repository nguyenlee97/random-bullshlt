import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const composer = readFileSync(
  new URL('../src/components/ChatPane/ChatComposer.jsx', import.meta.url),
  'utf8',
)
const demo = readFileSync(
  new URL('../src/demo/demoScripts.js', import.meta.url),
  'utf8',
)

test('composer uses Enter for newline and Ctrl or Command Enter for send', () => {
  assert.match(composer, /e\.key !== 'Enter'/)
  assert.match(composer, /e\.ctrlKey \|\| e\.metaKey/)
  assert.doesNotMatch(composer, /e\.key === 'Enter' && !e\.shiftKey/)
  assert.match(composer, /Enter để xuống dòng · Ctrl\/⌘\+Enter để gửi/)
  assert.match(composer, /Gửi tin nhắn \(Ctrl\/⌘\+Enter\)/)
})

test('composer does not submit while an IME is composing Vietnamese text', () => {
  assert.match(composer, /e\.nativeEvent\?\.isComposing/)
})

test('guided demo teaches the same keyboard contract', () => {
  assert.match(
    demo,
    /Enter để xuống dòng; Ctrl\/⌘\+Enter để gửi, hoặc bấm nút gửi/,
  )
  assert.doesNotMatch(demo, /Nhấn Enter để gửi/)
})
