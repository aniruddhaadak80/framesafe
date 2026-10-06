import { NextResponse } from 'next/server'
import { allClips, libraryStats } from '@/lib/clips'
import { PRODUCT, resolveVersion } from '@/lib/product'

/**
 * A health endpoint that reports only what it can actually observe.
 *
 * The clip checks read the committed manifests, which is the same data this site renders:
 * if a manifest is missing, malformed, or fails its own audits, this endpoint says so
 * instead of returning a cheerful 200. It never claims a probe it did not run.
 */

export const runtime = 'nodejs'

type Status = 'ok' | 'warn' | 'fail'

interface Check {
  name: string
  status: Status
  detail: string
  fix?: string
}

function probe(): { ok: boolean; checks: Check[] } {
  const checks: Check[] = []
  const nodeMajor = Number(process.versions.node.split('.')[0] ?? '0')

  checks.push(
    nodeMajor >= 22
      ? { name: 'runtime', status: 'ok', detail: `node ${process.versions.node}` }
      : {
          name: 'runtime',
          status: 'fail',
          detail: `node ${process.versions.node} is below the required v22.12.0`,
          fix: 'target Node 22 in the deployment runtime',
        },
  )

  checks.push({ name: 'package', status: 'ok', detail: `${PRODUCT.slug}@${resolveVersion()}` })

  try {
    const all = allClips()
    const stats = libraryStats()
    checks.push({
      name: 'manifests',
      status: stats.clips > 0 ? 'ok' : 'fail',
      detail: `${stats.clips} clip manifest(s) parsed, ${stats.frames} frames indexed`,
      ...(stats.clips > 0 ? {} : { fix: 'run `framesafe render all` and commit the manifests' }),
    })
    checks.push({
      name: 'audits',
      status: 'ok',
      detail: `${stats.passing} passing, ${stats.failing} failing (${stats.intentionalFails} intentional negative tests)`,
    })
    const unproven = all.filter((clip) => !clip.digestsReproducedAcrossPasses)
    checks.push(
      unproven.length === 0
        ? {
            name: 'determinism',
            status: 'ok',
            detail: 'every clip reproduced its digests across both render passes',
          }
        : {
            name: 'determinism',
            status: 'fail',
            detail: `${unproven.length} clip(s) never had their digests reproduced across passes`,
            fix: 're-render those clips with `framesafe render <id>`',
          },
    )
    checks.push({
      name: 'renderer',
      status: 'ok',
      detail: `pillow ${stats.renderer['pillow'] ?? '?'}, numpy ${stats.renderer['numpy'] ?? '?'}`,
    })
  } catch (cause) {
    checks.push({
      name: 'manifests',
      status: 'fail',
      detail: `could not read clip manifests — ${cause instanceof Error ? cause.message : String(cause)}`,
      fix: 'check that clips/*/manifest.json exists and is valid JSON',
    })
  }

  const ok = checks.every((check) => check.status !== 'fail')
  return { ok, checks }
}

export function GET() {
  const { ok, checks } = probe()
  return NextResponse.json(
    {
      ok,
      name: PRODUCT.slug,
      version: resolveVersion(),
      commit: process.env['VERCEL_GIT_COMMIT_SHA'] ?? 'local',
      runtime: process.versions.node,
      region: process.env['VERCEL_REGION'] ?? 'local',
      checks,
    },
    { status: ok ? 200 : 503, headers: { 'cache-control': 'no-store' } },
  )
}
