import { join } from 'node:path'
import { ToolRegistry, type Tool, type ToolContext } from '@framesafe/core'
import { buildRegistry } from '@framesafe/plugins'
import { loadCatalog } from '@framesafe/skills'
import { auditClipToRepo, listClips, readSpec, renderClipToRepo } from './clips.js'

export const ENGINE_MODULE = 'framesafe'

/**
 * Builds the one registry every surface shares.
 *
 * These tools are the product. A clip spec in, a compiled plan, a per-frame digest, an
 * audit verdict, a rendered MP4 — each one is arithmetic over rendered frames, reachable
 * identically from the CLI, the web app, and the MCP server.
 *
 * Every name matches ^[a-z][a-z0-9_]*$ so it is directly exposable over MCP.
 */
export function buildToolRegistry(cwd = process.cwd()): ToolRegistry {
  const registry = new ToolRegistry()
  const runEngine = async (op: string, input: unknown): Promise<unknown> => {
    const { EngineBridge } = await import('@framesafe/engine-client')
    const bridge = new EngineBridge({
      module: ENGINE_MODULE,
      cwd: join(cwd, 'services', 'engine', 'src'),
      timeoutMs: 20 * 60_000,
    })
    return await bridge.call({ op, input })
  }

  registry.register(
    {
      name: 'list_clips',
      description:
        'List every motion-graphics clip in the library with its frame count, verdict, and peak inter-frame motion. Use this first to discover clip ids before compiling, auditing, verifying or rendering one.',
      inputSchema: {
        type: 'object',
        properties: {
          failingOnly: { type: 'boolean', description: 'Only return clips whose verdict is not "pass".' },
        },
        additionalProperties: false,
      },
      outputSchema: {
        type: 'object',
        properties: {
          count: { type: 'number' },
          clips: { type: 'array', items: { type: 'object' } },
        },
        required: ['count', 'clips'],
      },
      permissions: ['fs:read'],
      surface: 'core',
      handler: async (input: { failingOnly?: boolean }) => {
        const clips = await listClips(cwd)
        const selected = input.failingOnly === true ? clips.filter((c) => c.verdict !== 'pass') : clips
        return { count: selected.length, clips: selected }
      },
    } satisfies Tool<{ failingOnly?: boolean }, unknown>,
    { source: 'core' },
  )

  registry.register(
    {
      name: 'compile_spec',
      description:
        'Compile a clip spec into a frame table: frame count, duration, per-layer windows, and the spec digest. Use this to check a spec is valid before rendering it, or to read exactly what a clip is made of.',
      inputSchema: {
        type: 'object',
        properties: {
          clip: { type: 'string', description: 'Clip id, e.g. "title-block".' },
          spec: { type: 'object', description: 'An inline spec document, instead of a clip id.' },
        },
        additionalProperties: false,
      },
      outputSchema: { type: 'object' },
      permissions: ['fs:read', 'proc:spawn'],
      surface: 'core',
      handler: async (input: { clip?: string; spec?: unknown }) => {
        const spec = input.spec ?? (await readSpec(cwd, input.clip as string))
        return await runEngine('compile', { spec })
      },
    } satisfies Tool<{ clip?: string; spec?: unknown }, unknown>,
    { source: 'core' },
  )

  registry.register(
    {
      name: 'audit_clip',
      description:
        "Re-run all three audits on a clip from its committed telemetry: flash safety (WCAG 2.3.1 style), continuity against the clip's declared budget, and the luminance envelope. Returns a verdict with an explicit reason per failing audit. Use this to decide whether a clip is safe to ship.",
      inputSchema: {
        type: 'object',
        properties: { clip: { type: 'string', description: 'Clip id to audit.' } },
        required: ['clip'],
        additionalProperties: false,
      },
      outputSchema: { type: 'object' },
      permissions: ['fs:read', 'fs:write', 'proc:spawn'],
      surface: 'core',
      handler: async (input: { clip: string }) => {
        const manifest = await auditClipToRepo(cwd, input.clip)
        return {
          id: manifest.id,
          frameCount: manifest.frameCount,
          verdict: manifest.verdict,
          failingAudits: manifest.failingAudits,
          reasons: manifest.reasons,
          audits: manifest.audits,
          rootDigest: manifest.rootDigest,
          specDigest: manifest.specDigest,
          renderer: manifest.renderer,
        }
      },
    } satisfies Tool<{ clip: string }, unknown>,
    { source: 'core' },
  )

  registry.register(
    {
      name: 'verify_clip',
      description:
        'Re-render every frame of a clip from its spec in a fresh engine process and compare the digests against the committed manifest. Use this to prove the library still renders byte-identically; it reports the first frame that differs.',
      inputSchema: {
        type: 'object',
        properties: { clip: { type: 'string', description: 'Clip id to verify.' } },
        required: ['clip'],
        additionalProperties: false,
      },
      outputSchema: { type: 'object' },
      permissions: ['fs:read', 'proc:spawn'],
      surface: 'core',
      handler: async (input: { clip: string }) => {
        const { readManifest } = await import('./clips.js')
        const spec = await readSpec(cwd, input.clip)
        const manifest = await readManifest(cwd, input.clip)
        if (manifest === null) {
          return {
            id: input.clip,
            reproducible: false,
            reason: 'no manifest committed for this clip — run render_clip first',
          }
        }
        return await runEngine('verify', { spec, manifest })
      },
    } satisfies Tool<{ clip: string }, unknown>,
    { source: 'core' },
  )

  registry.register(
    {
      name: 'frame_digest',
      description:
        'Return the sha256 digest of a single frame of a clip, plus the renderer versions that produced it. Use this to pin down exactly which frame changed when a verify fails.',
      inputSchema: {
        type: 'object',
        properties: {
          clip: { type: 'string', description: 'Clip id.' },
          frame: { type: 'number', description: 'Frame index, zero-based.', minimum: 0 },
        },
        required: ['clip', 'frame'],
        additionalProperties: false,
      },
      outputSchema: { type: 'object' },
      permissions: ['fs:read', 'proc:spawn'],
      surface: 'core',
      handler: async (input: { clip: string; frame: number }) => {
        const spec = await readSpec(cwd, input.clip)
        return await runEngine('digests', {
          spec,
          from: input.frame,
          to: input.frame + 1,
        })
      },
    } satisfies Tool<{ clip: string; frame: number }, unknown>,
    { source: 'core' },
  )

  registry.register(
    {
      name: 'render_clip',
      description:
        'Render a clip to H.264 MP4 and write its manifest. Two independent engine processes render the frames and their digests are compared before anything is written, so a non-deterministic render is refused rather than published.',
      inputSchema: {
        type: 'object',
        properties: {
          clip: { type: 'string', description: 'Clip id to render.' },
          crf: { type: 'number', description: 'H.264 quality, 0-51, lower is better.', minimum: 0 },
        },
        required: ['clip'],
        additionalProperties: false,
      },
      outputSchema: { type: 'object' },
      permissions: ['fs:read', 'fs:write', 'proc:spawn'],
      surface: 'core',
      handler: async (input: { clip: string; crf?: number }) => {
        const rendered = await renderClipToRepo(cwd, input.clip, {
          ...(input.crf !== undefined ? { crf: input.crf } : {}),
        })
        return {
          id: rendered.id,
          verdict: rendered.verdict,
          frames: rendered.manifest.frameCount,
          videoBytes: rendered.videoBytes,
          videoSha256: rendered.videoSha256,
          rootDigest: rendered.manifest.rootDigest,
          digestsReproducedAcrossPasses: rendered.digestsReproduced,
        }
      },
    } satisfies Tool<{ clip: string; crf?: number }, unknown>,
    { source: 'core' },
  )

  registry.register(
    {
      name: 'list_skills',
      description:
        'List the skill catalog with each skill name, version and description. Use this to discover what the agent can do before guessing a command.',
      inputSchema: {
        type: 'object',
        properties: {
          includeBodies: { type: 'boolean', description: 'Include each skill body.' },
        },
        additionalProperties: false,
      },
      outputSchema: {
        type: 'object',
        properties: {
          count: { type: 'number' },
          issues: { type: 'array', items: { type: 'string' } },
          skills: { type: 'array', items: { type: 'object' } },
        },
        required: ['count', 'issues', 'skills'],
      },
      permissions: ['fs:read'],
      surface: 'core',
      handler: async (input: { includeBodies?: boolean }) => {
        const { skills, issues } = loadCatalog(join(cwd, 'skills'))
        return {
          count: skills.length,
          issues: [...issues],
          skills: skills.map((skill) => ({
            name: skill.name,
            version: skill.version,
            description: skill.description,
            ...(input.includeBodies === true ? { body: skill.body } : {}),
          })),
        }
      },
    } satisfies Tool<{ includeBodies?: boolean }, unknown>,
    { source: 'core' },
  )

  registry.register(
    {
      name: 'list_plugins',
      description:
        'List the resolved plugin registry, including plugins that were shadowed, disabled or rejected and why. Use this to explain why an expected capability is missing.',
      inputSchema: { type: 'object', properties: {}, additionalProperties: false },
      outputSchema: { type: 'object' },
      permissions: ['fs:read'],
      surface: 'core',
      handler: async () => {
        const result = buildRegistry(join(cwd, 'plugins'))
        return {
          active: result.active.map((p) => ({
            name: p.manifest.name,
            version: p.manifest.version,
            capabilities: p.manifest.capabilities,
            shadowed: p.shadowed,
          })),
          disabled: result.disabled.map((p) => p.manifest.name),
          rejected: result.rejected.map((p) => ({ path: p.path, issues: p.issues })),
        }
      },
    } satisfies Tool<Record<string, never>, unknown>,
    { source: 'core' },
  )

  return registry
}

/** A minimal, dependency-free logger for the tool context. */
export function createContext(requestId = 'cli'): ToolContext {
  return {
    requestId,
    now: () => Date.now(),
    log: (level, message, fields) => {
      process.stderr.write(`${JSON.stringify({ level, message, requestId, ...fields })}\n`)
    },
    dataDir: process.env['PRODUCT_DATA_DIR'] ?? '.data',
  }
}
