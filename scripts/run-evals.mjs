#!/usr/bin/env node
// Run the audit eval suite and score it.
//
//   node scripts/run-evals.mjs [--json]
//
// Each case is a real spec plus the verdict and failing audits it must produce. A case is
// only scored when *both* match exactly: an audit that returns the right verdict for the
// wrong reason is not a pass, and neither is an audit that catches one breach but silently
// drops the second.
//
// Exit code 1 if any case fails, so the suite works as a gate.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { EngineBridge } from '@framesafe/engine-client'

const root = process.cwd()
const suite = JSON.parse(readFileSync(join(root, 'evals', 'cases.json'), 'utf8'))
const wantsJson = process.argv.includes('--json')

const bridge = new EngineBridge({
  module: 'framesafe',
  cwd: join(root, 'services', 'engine', 'src'),
  timeoutMs: 10 * 60_000,
})

const results = []
for (const testCase of suite.cases) {
  let actual
  let error
  try {
    actual = await bridge.call({ op: 'manifest', input: { spec: testCase.spec } })
  } catch (cause) {
    error = cause instanceof Error ? cause.message : String(cause)
  }

  const verdictOk = actual?.verdict === testCase.expect.verdict
  const auditsOk =
    JSON.stringify([...(actual?.failingAudits ?? [])].sort()) ===
    JSON.stringify([...testCase.expect.failingAudits].sort())

  results.push({
    id: testCase.id,
    passed: verdictOk && auditsOk && error === undefined,
    expectedVerdict: testCase.expect.verdict,
    actualVerdict: actual?.verdict ?? 'error',
    expectedAudits: testCase.expect.failingAudits,
    actualAudits: actual?.failingAudits ?? [],
    ...(error === undefined ? {} : { error }),
    peakDelta: actual?.telemetry?.peakDelta ?? null,
    maxFlashes: actual?.audits?.flash?.maxFlashesInWindow ?? null,
  })
}

const passed = results.filter((result) => result.passed).length
const score = results.length === 0 ? 0 : passed / results.length

if (wantsJson) {
  console.log(JSON.stringify({ score, passed, total: results.length, results }, null, 2))
} else {
  console.log('  case                  verdict   audits              result')
  for (const result of results) {
    console.log(
      `  ${result.id.padEnd(21)} ${String(result.actualVerdict).padEnd(8)} ` +
        `${(result.actualAudits.join(',') || '-').padEnd(18)} ` +
        `${result.passed ? 'pass' : 'FAIL'}`,
    )
    if (!result.passed) {
      console.log(
        `    expected ${result.expectedVerdict} [${result.expectedAudits.join(',') || '-'}]` +
          (result.error === undefined ? '' : ` error: ${result.error}`),
      )
    }
  }
  console.log(`\n  ${passed}/${results.length} cases passed (score ${score.toFixed(2)})`)
}

process.exit(passed === results.length ? 0 : 1)
