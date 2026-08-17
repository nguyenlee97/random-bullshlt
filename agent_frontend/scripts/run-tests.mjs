import { readdir } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const projectRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const testsDirectory = join(projectRoot, 'tests')
const testFiles = (await readdir(testsDirectory))
  .filter((file) => file.endsWith('.test.mjs'))
  .sort()
  .map((file) => join(testsDirectory, file))

if (testFiles.length === 0) {
  throw new Error(`No frontend test files found in ${testsDirectory}`)
}

const result = spawnSync(process.execPath, ['--test', ...testFiles], {
  cwd: projectRoot,
  stdio: 'inherit',
})

process.exit(result.status ?? 1)
