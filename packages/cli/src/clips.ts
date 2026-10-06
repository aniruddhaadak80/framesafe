import { existsSync, readdirSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { NotFoundError, UpstreamError } from '@framesafe/core'
import type { ClipInput } from '@framesafe/memory'
import {
  buildManifest,
  renderClip,
  sha256File,
  type ClipManifest,
  type ClipSpec,
} from '@framesafe/engine-client'

/**
 * The repository's clip layout, in one place.
 *
 * `clips/<id>/spec.json` is the source of truth, `clips/<id>/manifest.json` is the committed
 * proof, and `apps/web/public/clips/<id>.mp4` is the encoded artefact the site serves. The
 * CLI, the MCP tools, and the render script all go through this module, so there is one
 * definition of where a clip lives rather than three.
 */

export interface ClipSpecFile extends ClipSpec {
  readonly id: string
  readonly title: string
  readonly summary: string
  readonly technique: readonly string[]
  readonly tags: readonly string[]
  readonly fps: number
  readonly width: number
  readonly height: number
  readonly durationMs: number
  readonly frameCount?: number
}

export interface ClipSummary {
  readonly id: string
  readonly title: string
  readonly summary: string
  readonly technique: readonly string[]
  readonly tags: readonly string[]
  readonly frameCount: number
  readonly fps: number
  readonly width: number
  readonly height: number
  readonly durationMs: number
  readonly verdict: string
  readonly failingAudits: readonly string[]
  readonly reasons: readonly string[]
  readonly rootDigest: string
  readonly specDigest: string
  readonly video: { readonly file: string; readonly bytes: number; readonly sha256: string } | null
  readonly peakDelta: number
  readonly maxFlashesInWindow: number
  readonly hasManifest: boolean
}

/** Walk up from `start` until the repository root is found. */
export function findRepoRoot(start: string = process.cwd()): string {
  let current = resolve(start)
  for (let depth = 0; depth < 8; depth += 1) {
    if (existsSync(join(current, 'clips')) && existsSync(join(current, 'package.json'))) {
      return current
    }
    const parent = dirname(current)
    if (parent === current) break
    current = parent
  }
  throw new UpstreamError('could not locate the framesafe repository root', { start })
}

export function clipsDir(root: string): string {
  return join(root, 'clips')
}

export function videoDir(root: string): string {
  return join(root, 'apps', 'web', 'public', 'clips')
}

export function listClipIds(root: string): string[] {
  const dir = clipsDir(root)
  if (!existsSync(dir)) return []
  return readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && existsSync(join(dir, entry.name, 'spec.json')))
    .map((entry) => entry.name)
    .sort()
}

export async function readSpec(root: string, id: string): Promise<ClipSpecFile> {
  const path = join(clipsDir(root), id, 'spec.json')
  if (!existsSync(path)) {
    throw new NotFoundError(`no clip spec at ${path}`, { clip: id, known: listClipIds(root) })
  }
  return JSON.parse(await readFile(path, 'utf8')) as ClipSpecFile
}

export async function readManifest(root: string, id: string): Promise<ClipManifest | null> {
  const path = join(clipsDir(root), id, 'manifest.json')
  if (!existsSync(path)) return null
  return JSON.parse(await readFile(path, 'utf8')) as ClipManifest
}

export async function writeManifest(root: string, id: string, manifest: unknown): Promise<void> {
  const path = join(clipsDir(root), id, 'manifest.json')
  await mkdir(dirname(path), { recursive: true })
  await writeFile(path, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
}

function manifestSummary(id: string, spec: ClipSpecFile, manifest: ClipManifest | null): ClipSummary {
  const telemetry = manifest?.telemetry
  const video = manifest?.video ?? null
  return {
    id,
    title: manifest?.title ?? spec.title,
    summary: manifest?.summary ?? spec.summary,
    technique: manifest?.technique ?? spec.technique,
    tags: manifest?.tags ?? spec.tags,
    frameCount: manifest?.frameCount ?? spec.frameCount ?? 0,
    fps: spec.fps,
    width: spec.width,
    height: spec.height,
    durationMs: spec.durationMs,
    verdict: manifest?.verdict ?? 'unverified',
    failingAudits: manifest?.failingAudits ?? [],
    reasons: manifest?.reasons ?? [],
    rootDigest: manifest?.rootDigest ?? 'none',
    specDigest: manifest?.specDigest ?? 'none',
    video,
    peakDelta: telemetry?.peakDelta ?? 0,
    maxFlashesInWindow: manifest?.audits.flash.maxFlashesInWindow ?? 0,
    hasManifest: manifest !== null,
  }
}

/** Every clip with its committed verdict. The gallery and `framesafe clips` read this. */
export async function listClips(root: string): Promise<ClipSummary[]> {
  const ids = listClipIds(root)
  const summaries = await Promise.all(
    ids.map(async (id) => manifestSummary(id, await readSpec(root, id), await readManifest(root, id))),
  )
  return summaries
}

export async function getClip(root: string, id: string): Promise<ClipSummary> {
  if (!listClipIds(root).includes(id)) {
    throw new NotFoundError(`unknown clip "${id}"`, { clip: id, known: listClipIds(root) })
  }
  return manifestSummary(id, await readSpec(root, id), await readManifest(root, id))
}

export interface RenderedClip {
  readonly id: string
  readonly manifest: ClipManifest
  readonly videoPath: string
  readonly videoBytes: number
  readonly videoSha256: string
  readonly digestsReproduced: boolean
  readonly firstMismatchFrame: number | null
  readonly verdict: string
}

/**
 * Render one clip end to end and commit both artefacts.
 *
 * The manifest is written only after the streaming pass has reproduced the manifest pass's
 * digests. A clip whose two renders disagree is not published: it is a bug in the renderer,
 * and shipping it would make every later verification meaningless.
 */
export async function renderClipToRepo(
  root: string,
  id: string,
  options: { crf?: number; onProgress?: (frame: number, total: number) => void } = {},
): Promise<RenderedClip> {
  const spec = await readSpec(root, id)
  const videoPath = join(videoDir(root), `${id}.mp4`)
  const result = await renderClip(spec, {
    root,
    outFile: videoPath,
    ...(options.crf !== undefined ? { crf: options.crf } : {}),
    ...(options.onProgress !== undefined ? { onProgress: options.onProgress } : {}),
  })

  if (!result.digestsReproduced) {
    throw new UpstreamError(
      `renderer is not deterministic for "${id}" — frame ${
        result.firstMismatchFrame ?? '?'
      } differed between the manifest pass and the streaming pass`,
      { clip: id, firstMismatchFrame: result.firstMismatchFrame },
    )
  }

  const manifest = {
    ...result.manifest,
    video: {
      file: `/clips/${id}.mp4`,
      bytes: result.video.bytes,
      sha256: result.video.sha256,
      encoder: result.video.encoder,
    },
    digestsReproducedAcrossPasses: true,
  }
  await writeManifest(root, id, manifest)

  return {
    id,
    manifest: manifest as ClipManifest,
    videoPath,
    videoBytes: result.video.bytes,
    videoSha256: result.video.sha256,
    digestsReproduced: true,
    firstMismatchFrame: null,
    verdict: result.manifest.verdict,
  }
}

/** Re-derive the manifest without encoding: digests, telemetry, audits. */
export async function auditClipToRepo(root: string, id: string): Promise<ClipManifest> {
  const spec = await readSpec(root, id)
  const manifest = await buildManifest(spec, { root })
  const existing = await readManifest(root, id)
  const videoPath = join(videoDir(root), `${id}.mp4`)
  const hasVideo = existsSync(videoPath)
  const merged = {
    ...manifest,
    ...(hasVideo
      ? {
          video: {
            file: `/clips/${id}.mp4`,
            bytes: (await statSafe(videoPath)) ?? 0,
            sha256: await sha256File(videoPath),
            encoder:
              existing?.['video'] !== undefined
                ? ((existing['video'] as { encoder?: string }).encoder ?? 'unknown')
                : 'unknown',
          },
        }
      : {}),
    digestsReproducedAcrossPasses: existing?.['digestsReproducedAcrossPasses'] ?? false,
  }
  await writeManifest(root, id, merged)
  return merged as ClipManifest
}

async function statSafe(path: string): Promise<number | null> {
  const { stat } = await import('node:fs/promises')
  try {
    return (await stat(path)).size
  } catch {
    return null
  }
}

/** Where the derived index lives. Gitignored; rebuildable from the manifests at any time. */
export function indexPath(root: string): string {
  return join(root, '.data', 'framesafe.db')
}

/**
 * Record a completed render or audit into the derived index.
 *
 * This runs from the CLI rather than from a tool handler on purpose: MCP tools are
 * stateless, and a durable run log is state that belongs to the operator surface.
 */
export async function recordClipRun(
  root: string,
  manifest: ClipManifest,
  op: 'render' | 'audit',
  detail?: string,
): Promise<void> {
  const { mkdir } = await import('node:fs/promises')
  const { ClipIndex, Store } = await import('@framesafe/memory')
  await mkdir(dirname(indexPath(root)), { recursive: true })
  const store = new Store(indexPath(root))
  try {
    const index = new ClipIndex(store)
    index.upsertClip(
      {
        id: manifest.id,
        title: manifest.title,
        verdict: manifest.verdict,
        frameCount: manifest.frameCount,
        fps: manifest.fps,
        rootDigest: manifest.rootDigest,
        specDigest: manifest.specDigest,
        peakDelta: manifest.telemetry.peakDelta,
        failingAudits: manifest.failingAudits,
        videoBytes: manifest.video?.bytes ?? 0,
        manifest: manifest,
      },
      Date.now(),
    )
    index.recordRun(
      { clip: manifest.id, op, verdict: manifest.verdict, ...(detail !== undefined ? { detail } : {}) },
      Date.now(),
    )
  } finally {
    store.close()
  }
}

/** Rebuild the whole index from every committed manifest. */
export async function rebuildIndex(root: string): Promise<{
  clips: number
  passing: number
  failing: number
  runs: number
}> {
  const { mkdir } = await import('node:fs/promises')
  const { ClipIndex, Store } = await import('@framesafe/memory')
  await mkdir(dirname(indexPath(root)), { recursive: true })
  const ids = listClipIds(root)
  const store = new Store(indexPath(root))
  try {
    const index = new ClipIndex(store)
    const inputs: ClipInput[] = []
    for (const id of ids) {
      const manifest = await readManifest(root, id)
      if (manifest === null) continue
      inputs.push({
        id: manifest.id,
        title: manifest.title,
        verdict: manifest.verdict,
        frameCount: manifest.frameCount,
        fps: manifest.fps,
        rootDigest: manifest.rootDigest,
        specDigest: manifest.specDigest,
        peakDelta: manifest.telemetry.peakDelta,
        failingAudits: manifest.failingAudits,
        videoBytes: manifest.video?.bytes ?? 0,
        manifest,
      })
    }
    const stats = index.rebuild(inputs, Date.now())
    return { clips: stats.clips, passing: stats.passing, failing: stats.failing, runs: stats.runs }
  } finally {
    store.close()
  }
}

/** Read recent runs out of the index. Returns null when no index exists yet. */
export async function readRuns(
  root: string,
  clip: string | undefined,
  limit: number,
): Promise<
  | readonly {
      id: number
      clip: string
      op: string
      verdict: string | null
      detail: string | null
      created_at: number
    }[]
  | null
> {
  const { existsSync } = await import('node:fs')
  if (!existsSync(indexPath(root))) return null
  const { ClipIndex, Store } = await import('@framesafe/memory')
  const store = new Store(indexPath(root))
  try {
    const index = new ClipIndex(store)
    return index.listRuns(clip, limit)
  } finally {
    store.close()
  }
}
