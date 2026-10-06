import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

/**
 * The clip library, read from the committed manifests.
 *
 * `clips/<id>/manifest.json` is the single source of truth and is what this module reads.
 * Nothing here re-derives a verdict: the site shows what the engine committed, so the
 * gallery and `framesafe audit` can never disagree.
 *
 * Reading happens at build time and the pages are statically generated, which is why the
 * deployed site needs no database and no runtime filesystem.
 */

export interface Telemetry {
  readonly luma: readonly number[]
  readonly delta: readonly number[]
  readonly flashFrames: readonly number[]
  readonly peakDelta: number
  readonly worstDeltaFrame: number
}

export interface AuditResult {
  readonly name: string
  readonly passed: boolean
  readonly reason: string
  readonly budget?: number
  readonly peakDelta?: number
  readonly peakFrame?: number
  readonly maxFlashesInWindow?: number
  readonly windowStartFrame?: number | null
  readonly firstFlashFrame?: number | null
  readonly minLuma?: number
  readonly maxLuma?: number
  readonly meanLuma?: number
  readonly range?: number
  readonly overBudgetBy?: number
  readonly worstAdjacentDelta?: number
  readonly worstAdjacentFrame?: number
}

export interface ClipVideo {
  readonly file: string
  readonly bytes: number
  readonly sha256: string
  readonly encoder: string
}

export interface Clip {
  readonly id: string
  readonly title: string
  readonly summary: string
  readonly technique: readonly string[]
  readonly tags: readonly string[]
  readonly fps: number
  readonly width: number
  readonly height: number
  readonly durationMs: number
  readonly frameCount: number
  readonly specDigest: string
  readonly rootDigest: string
  readonly continuityBudget: number
  readonly maxAdjacentContrast: number
  readonly reducedMotion: { readonly holdFrame: number; readonly note: string }
  readonly renderer: Record<string, string>
  readonly telemetry: Telemetry
  readonly audits: Record<string, AuditResult>
  readonly verdict: string
  readonly failingAudits: readonly string[]
  readonly reasons: readonly string[]
  readonly frames: readonly { readonly i: number; readonly digest: string }[]
  readonly video: ClipVideo | null
  readonly digestsReproducedAcrossPasses: boolean
  /** True when the clip ships as a deliberate negative test. */
  readonly intentionalFail: boolean
}

export function repoRoot(): string {
  let current = resolve(process.cwd())
  for (let depth = 0; depth < 8; depth += 1) {
    if (existsSync(join(current, 'clips')) && existsSync(join(current, 'package.json'))) return current
    const parent = resolve(current, '..')
    if (parent === current) break
    current = parent
  }
  throw new Error('could not locate the framesafe repository root from ' + process.cwd())
}

function isClip(value: unknown): value is Clip {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as { id?: unknown }).id === 'string' &&
    typeof (value as { verdict?: unknown }).verdict === 'string' &&
    Array.isArray((value as { frames?: unknown }).frames)
  )
}

let cache: readonly Clip[] | null = null

/** Every clip that has a committed manifest, sorted by id. Memoised per server process. */
export function allClips(): readonly Clip[] {
  if (cache !== null) return cache
  const root = join(repoRoot(), 'clips')
  const clips: Clip[] = []
  for (const id of directoryNames(root)) {
    const path = join(root, id, 'manifest.json')
    if (!existsSync(path)) continue
    const parsed: unknown = JSON.parse(readFileSync(path, 'utf8'))
    if (!isClip(parsed)) continue
    clips.push({ ...parsed, intentionalFail: parsed.tags.includes('intentional-fail') })
  }
  cache = clips.sort((a, b) => a.id.localeCompare(b.id))
  return cache
}

function directoryNames(root: string): readonly string[] {
  if (!existsSync(root)) return []
  return readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort()
}

export function clipById(id: string): Clip | undefined {
  return allClips().find((clip) => clip.id === id)
}

export interface LibraryStats {
  readonly clips: number
  readonly passing: number
  readonly failing: number
  readonly intentionalFails: number
  readonly frames: number
  readonly videoBytes: number
  readonly techniques: readonly string[]
  readonly renderer: Record<string, string>
  readonly maxPeakDelta: number
  readonly maxFlashesInWindow: number
}

export function libraryStats(): LibraryStats {
  const clips = allClips()
  const renderer: Record<string, string> = {}
  let frames = 0
  let bytes = 0
  let peak = 0
  let flashes = 0
  const techniques = new Set<string>()
  for (const clip of clips) {
    Object.assign(renderer, clip.renderer)
    frames += clip.frameCount
    bytes += clip.video?.bytes ?? 0
    peak = Math.max(peak, clip.telemetry.peakDelta)
    flashes = Math.max(flashes, clip.audits['flash']?.maxFlashesInWindow ?? 0)
    for (const technique of clip.technique) techniques.add(technique)
  }
  return {
    clips: clips.length,
    passing: clips.filter((clip) => clip.verdict === 'pass').length,
    failing: clips.filter((clip) => clip.verdict !== 'pass').length,
    intentionalFails: clips.filter((clip) => clip.intentionalFail).length,
    frames,
    videoBytes: bytes,
    techniques: [...techniques].sort(),
    renderer,
    maxPeakDelta: peak,
    maxFlashesInWindow: flashes,
  }
}

/** A short digest for display. Never use this to compare frames. */
export function shortDigest(digest: string): string {
  return digest.replace(/^sha256:/, '').slice(0, 12)
}
