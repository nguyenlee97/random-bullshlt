import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from '../agent_frontend/node_modules/@babel/parser/lib/index.js'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(scriptDir, '..')
const frontendRoot = path.join(root, 'agent_frontend', 'src')
const outputPath = path.join(root, 'docs', 'copy-review', '05-raw-source-literals.md')

const explicitFiles = [
  'App.jsx',
  'api/agentApi.js',
  'hooks/useChat.js',
]

const includedDirectories = [
  'components',
  'demo',
  'steps',
]

const ignoredFiles = new Set([
  'components/ui/button.jsx',
  'components/ui/card.jsx',
  'components/ui/dialog.jsx',
  'components/ui/input.jsx',
  'components/ui/label.jsx',
  'components/ui/progress.jsx',
  'components/ui/scroll-area.jsx',
  'components/ui/select.jsx',
  'components/ui/separator.jsx',
  'components/ui/textarea.jsx',
  'components/ui/tooltip.jsx',
])

const ignoredAttributeNames = new Set([
  'className',
  'data-demo',
  'data-mode',
  'data-state',
  'href',
  'id',
  'key',
  'name',
  'role',
  'target',
  'type',
  'value',
])

const codeOnlyPatterns = [
  /^[a-z0-9_-]+$/i,
  /^[A-Z0-9_]+$/,
  /^#[0-9a-f]{3,8}$/i,
  /^(GET|POST|PUT|PATCH|DELETE)\s+\//,
  /^[/.][^\s]+$/,
  /^(sm|md|lg|xl|2xl):/,
]

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const absolute = path.join(directory, entry.name)
    if (entry.isDirectory()) return walk(absolute)
    return /\.(jsx?|mjs)$/.test(entry.name) ? [absolute] : []
  })
}

function normalize(value) {
  return String(value)
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map(part => part.trim())
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function templateValue(node) {
  const parts = []
  node.quasis.forEach((quasi, index) => {
    parts.push(quasi.value.cooked || quasi.value.raw)
    if (index < node.expressions.length) parts.push(`{expression_${index + 1}}`)
  })
  return normalize(parts.join(''))
}

function looksUserFacing(value, context = {}) {
  if (!value || value.length < 2) return false
  if (context.attribute && ignoredAttributeNames.has(context.attribute)) return false
  if (/^(https?:|data:|blob:)/i.test(value)) return false
  if (/^[\d.,:;/×%+\-–—()\s]+$/.test(value)) return false
  if (codeOnlyPatterns.some(pattern => pattern.test(value))) return false
  if (value.includes('className=') || value.includes('data-demo=')) return false

  const hasVietnamese = /[À-ỹĐđ]/.test(value)
  const tokens = value.split(/\s+/)
  const cssLikeTokens = tokens.filter(token =>
    /[:[\]/]/.test(token)
    || /^(?:bg|text|border|hover|focus|active|disabled|group|peer|grid|flex|items|justify|gap|space|rounded|shadow|ring|transition|duration|ease|opacity|overflow|whitespace|break|object|absolute|relative|fixed|sticky|inset|top|right|bottom|left|z|w|h|min|max|p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml)-/.test(token)
  ).length
  if (!hasVietnamese && tokens.length > 1 && cssLikeTokens / tokens.length >= 0.5) {
    return false
  }
  const hasSentenceShape = /\s/.test(value) && /[A-Za-zÀ-ỹ]/.test(value)
  const isKnownShortLabel = /^(AI|OA|KPI|FAQ|Chat|Brief|Audience|Creative|Setup|Report|Email|Docs|Tour|Workspace|Autopilot|Copilot|Live)$/i.test(value)
  return hasVietnamese || hasSentenceShape || isKnownShortLabel
}

function visit(node, parent, collect) {
  if (!node || typeof node !== 'object') return

  if (node.type === 'JSXText') {
    const value = normalize(node.value)
    if (looksUserFacing(value)) collect(node, value, 'JSX text')
  }

  if (node.type === 'JSXAttribute') {
    const attribute = node.name?.name
    if (node.value?.type === 'StringLiteral') {
      const value = normalize(node.value.value)
      if (looksUserFacing(value, { attribute })) {
        collect(node.value, value, `attribute: ${attribute}`)
      }
    } else if (node.value?.type === 'JSXExpressionContainer') {
      const expression = node.value.expression
      if (expression?.type === 'StringLiteral') {
        const value = normalize(expression.value)
        if (looksUserFacing(value, { attribute })) {
          collect(expression, value, `attribute: ${attribute}`)
        }
      } else if (expression?.type === 'TemplateLiteral') {
        const value = templateValue(expression)
        if (looksUserFacing(value, { attribute })) {
          collect(expression, value, `attribute: ${attribute}`)
        }
      }
    }
  }

  if (node.type === 'StringLiteral') {
    const isHandledAttribute = parent?.type === 'JSXAttribute'
    const isImport = ['ImportDeclaration', 'ExportNamedDeclaration', 'ExportAllDeclaration'].includes(parent?.type)
    const value = normalize(node.value)
    if (!isHandledAttribute && !isImport && looksUserFacing(value)) {
      collect(node, value, 'string')
    }
  }

  if (node.type === 'TemplateLiteral') {
    const isHandledAttribute = parent?.type === 'JSXExpressionContainer'
      && parent.__copyReviewAttribute === true
    const value = templateValue(node)
    if (!isHandledAttribute && looksUserFacing(value)) {
      collect(node, value, 'template')
    }
  }

  for (const [key, child] of Object.entries(node)) {
    if (['loc', 'start', 'end', 'extra'].includes(key)) continue
    if (Array.isArray(child)) {
      child.forEach(item => visit(item, node, collect))
    } else if (child && typeof child === 'object' && child.type) {
      if (node.type === 'JSXAttribute' && key === 'value') {
        child.__copyReviewAttribute = true
      }
      visit(child, node, collect)
    }
  }
}

const files = [
  ...explicitFiles.map(file => path.join(frontendRoot, file)),
  ...includedDirectories.flatMap(directory => walk(path.join(frontendRoot, directory))),
]
  .filter((file, index, all) => all.indexOf(file) === index)
  .filter(file => !ignoredFiles.has(path.relative(frontendRoot, file).replaceAll('\\', '/')))
  .sort()

const sections = []
let total = 0

for (const absolutePath of files) {
  const relative = path.relative(root, absolutePath).replaceAll('\\', '/')
  const source = fs.readFileSync(absolutePath, 'utf8')
  const ast = parse(source, {
    sourceType: 'module',
    plugins: ['jsx', 'optionalChaining', 'nullishCoalescingOperator'],
    errorRecovery: true,
  })
  const entries = []
  const seen = new Set()

  visit(ast.program, null, (node, value, kind) => {
    const line = node.loc?.start?.line || 1
    const key = `${line}:${value}`
    if (seen.has(key)) return
    seen.add(key)
    entries.push({ line, value, kind })
  })

  entries.sort((a, b) => a.line - b.line || a.value.localeCompare(b.value, 'vi'))
  if (!entries.length) continue
  total += entries.length

  sections.push(`## \`${relative}\`\n`)
  sections.push('| Line | Kind | Literal copy |')
  sections.push('| ---: | --- | --- |')
  for (const entry of entries) {
    const escaped = entry.value
      .replaceAll('\\', '\\\\')
      .replaceAll('|', '\\|')
      .replaceAll('`', '\\`')
    sections.push(`| ${entry.line} | ${entry.kind} | ${escaped} |`)
  }
  sections.push('')
}

const output = [
  '# Raw frontend source-literal inventory',
  '',
  'This file is generated from the current frontend source. It is a completeness',
  'appendix for wording review, not a proposed rewrite. It intentionally includes',
  'some internal-looking labels when the extractor cannot prove that a literal is',
  'invisible. Review the curated documents 01–04 first, then use this file to catch',
  'short labels, conditional states, and fallback branches.',
  '',
  `Generated: ${new Date().toISOString()}`,
  `Candidate literals: ${total}`,
  '',
  ...sections,
].join('\n')

fs.writeFileSync(outputPath, output, 'utf8')
console.log(`Wrote ${total} candidate literals to ${path.relative(root, outputPath)}`)
