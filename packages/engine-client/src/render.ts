import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { mkdir, stat } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { Writable } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { UpstreamError } from '@framesafe/core'
import { EngineBridge } from './bridge.js'

const require = createRequire(import.meta.url)

/** A clip spec, exactly as it appears in `clips/<id>/spec.json`. */
export interface ClipSpec {
  readonly id: string
  readonly fps: number
  readonly width: number
  readonly height: number
  readonly [key: string]: unknown
}

export interface ClipManifest {
  readonly schema: number
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
  readonly rootDigest: string
  readonly specDigest: string
  readonly continuityBudget: number
  readonly maxAdjacentContrast: number
  readonly reducedMotion: { readonly holdFrame: number; readonly note: string }
  readonly renderer: Record<string, string>
  readonly frames: readonly { readonly i: number; readonly digest: string }[]
  readonly telemetry: {
    readonly luma: readonly number[]
    readonly delta: readonly number[]
    readonly flashFrames: readonly number[]
    readonly peakDelta: number
    readonly worstDeltaFrame: number
  }
  readonly audits: {
    readonly flash: { readonly passed: boolean; readonly reason: string; readonly maxFlashesInWindow: number }
    readonly continuity: {
      readonly passed: boolean
      readonly reason: string
      readonly budget: number
      readonly peakDelta: number
      readonly peakFrame: number
    }
    readonly luminance: { readonly passed: boolean; readonly reason: string; readonly range: number }
  }
  readonly verdict: string
  readonly failingAudits: readonly string[]
  readonly reasons: readonly string[]
  readonly video?: {
    readonly file: string
    readonly bytes: number
    readonly sha256: string
    readonly encoder: string
  }
  readonly digestsReproducedAcrossPasses?: boolean
}

export interface RenderResult {
  readonly manifest: ClipManifest
  readonly video: {
    readonly file: string
    readonly bytes: number
    readonly sha256: string
    readonly encoder: string
  }
  /** Digests recomputed by the streaming pass, compared against the manifest's. */
  readonly digestsReproduced: boolean
  readonly firstMismatchFrame: number | null
}

export interface BuildManifestOptions {
  readonly root: string
  readonly python?: string
}

export interface EncodeOptions extends BuildManifestOptions {
  readonly outFile: string
  /** H.264 quality: lower is better. 20 is visually lossless for flat vector art. */
  readonly crf?: number
  readonly onProgress?: (frame: number, total: number) => void
}

/**
 * Resolve the bundled ffmpeg binary.
 *
 * Encoding is a host concern on purpose: the engine renders pixels and never spawns a
 * process, so a codec upgrade can change the MP4 without changing a single frame digest.
 */
export function ffmpegPath(): string {
  const override = process.env['FFMPEG_PATH']
  if (override !== undefined && override.length > 0) return override
  try {
    const resolved = require('ffmpeg-static') as string | null
    if (typeof resolved === 'string' && resolved.length > 0) return resolved
  } catch {
    /* fall through to the actionable error below */
  }
  throw new UpstreamError(
    'ffmpeg binary not found — run `npm install` (ffmpeg-static ships the binary) or set FFMPEG_PATH',
    { hint: 'npm install && npm run render -- <clip>' },
  )
}

function encoderArgs(options: {
  width: number
  height: number
  fps: number
  outFile: string
  crf: number
}): string[] {
  return [
    '-hide_banner',
    '-loglevel',
    'error',
    '-y',
    '-f',
    'rawvideo',
    '-pix_fmt',
    'rgb24',
    '-s',
    `${options.width}x${options.height}`,
    '-r',
    String(options.fps),
    '-i',
    'pipe:0',
    '-an',
    '-c:v',
    'libx264',
    '-preset',
    'medium',
    '-crf',
    String(options.crf),
    '-pix_fmt',
    'yuv420p',
    '-movflags',
    '+faststart',
    options.outFile,
  ]
}

/** Ask the engine for the manifest: digests, telemetry, audits. Renders every frame. */
export async function buildManifest(spec: ClipSpec, options: BuildManifestOptions): Promise<ClipManifest> {
  const bridge = new EngineBridge({
    module: 'framesafe',
    cwd: join(options.root, 'services', 'engine', 'src'),
    ...(options.python !== undefined ? { python: options.python } : {}),
    timeoutMs: 20 * 60_000,
  })
  return await bridge.call<ClipManifest>({ op: 'manifest', input: { spec } })
}

/**
 * Render a clip to an MP4.
 *
 * Two independent engine processes render the frames: one computes the manifest, one
 * streams pixels into the encoder. The streaming pass digests what it actually encoded and
 * the result is compared frame by frame against the manifest, so a non-deterministic
 * renderer fails here rather than being discovered later by a reviewer.
 */
export async function renderClip(spec: ClipSpec, options: EncodeOptions): Promise<RenderResult> {
  const crf = options.crf ?? 20
  const manifest = await buildManifest(spec, options)
  const total = manifest.frameCount
  await mkdir(dirname(options.outFile), { recursive: true })

  const encoder = spawn(
    ffmpegPath(),
    encoderArgs({
      width: manifest.width,
      height: manifest.height,
      fps: manifest.fps,
      outFile: options.outFile,
      crf,
    }),
    { stdio: ['pipe', 'ignore', 'pipe'] },
  )
  const encoderErrors: string[] = []
  encoder.stderr.on('data', (chunk: Buffer) => encoderErrors.push(chunk.toString('utf8')))

  const renderer = spawn(options.python ?? 'python', ['-m', 'framesafe', '--stream'], {
    cwd: join(options.root, 'services', 'engine', 'src'),
    stdio: ['pipe', 'pipe', 'pipe'],
  })
  renderer.stdout.pipe(encoder.stdin)
  const progressLines: string[] = []
  renderer.stderr.on('data', (chunk: Buffer) => progressLines.push(chunk.toString('utf8')))
  renderer.stdin.end(JSON.stringify({ op: 'render_stream', input: { spec } }))

  const rendererExit = await new Promise<number>((resolve) => {
    renderer.on('error', () => resolve(-1))
    renderer.on('close', (code) => resolve(code ?? -1))
  })
  const encoderExit = await new Promise<number>((resolve) => {
    encoder.on('error', () => resolve(-1))
    encoder.on('close', (code) => resolve(code ?? -1))
  })

  if (rendererExit !== 0) {
    throw new UpstreamError(`engine stream pass exited ${rendererExit}`, { spec: spec.id })
  }
  if (encoderExit !== 0) {
    throw new UpstreamError(`ffmpeg exited ${encoderExit}: ${encoderErrors.join('').trim()}`, {
      exitCode: encoderExit,
      outFile: options.outFile,
    })
  }

  const reproduced: string[] = []
  for (const line of progressLines.join('').split(/\r?\n/)) {
    const match = /^frame (\d+) (\S+)$/.exec(line.trim())
    if (match?.[1] !== undefined && match[2] !== undefined) reproduced.push(match[2])
  }

  let firstMismatchFrame: number | null = null
  const shared = Math.max(manifest.frames.length, reproduced.length)
  for (let index = 0; index < shared; index += 1) {
    if (manifest.frames[index]?.digest !== reproduced[index]) {
      firstMismatchFrame = index
      break
    }
  }
  options.onProgress?.(reproduced.length, total)

  const info = await stat(options.outFile)
  return {
    manifest,
    video: {
      file: options.outFile,
      bytes: info.size,
      sha256: await sha256File(options.outFile),
      encoder: `libx264 crf ${crf} yuv420p`,
    },
    digestsReproduced: firstMismatchFrame === null && reproduced.length === total,
    firstMismatchFrame,
  }
}

/** A sha256 of a file, streamed so a large video never lands in memory. */
export async function sha256File(path: string): Promise<string> {
  const hash = createHash('sha256')
  const sink = new Writable({
    write(chunk: Buffer, _encoding, done) {
      hash.update(chunk)
      done()
    },
  })
  await pipeline(createReadStream(path), sink)
  return `sha256:${hash.digest('hex')}`
}
