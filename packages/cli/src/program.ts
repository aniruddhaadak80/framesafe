import { readFile } from 'node:fs/promises'
import { Command } from 'commander'
import { join } from 'node:path'
import { EngineBridge } from '@framesafe/engine-client'
import { buildToolRegistry, createContext } from './bootstrap.js'
import {
  auditClipToRepo,
  findRepoRoot,
  listClipIds,
  indexPath,
  listClips,
  readManifest,
  readRuns,
  rebuildIndex,
  recordClipRun,
  readSpec,
  renderClipToRepo,
} from './clips.js'
import { doctor, renderReport } from './doctor.js'

const VERSION = '0.1.0'

/** A usage error: exit code 2, never 1. */
class UsageError extends Error {}

/** Exit codes are part of the contract: 0 ok, 1 runtime failure, 2 usage error. */
export function buildProgram(): Command {
  const program = new Command()

  program
    .name('framesafe')
    .description(
      'framesafe — compile a motion-graphics spec into frame-exact renders, then prove each clip reproducible, motion-safe and inside its declared continuity budget.',
    )
    .version(VERSION, '-v, --version', 'print the version')
    .exitOverride((error) => {
      process.exitCode = error.exitCode === 0 ? 0 : 2
      throw error
    })

  const wantsJson = (): boolean => process.argv.includes('--json')
  const say = (line: string): void => {
    process.stdout.write(`${line}\n`)
  }

  const guard = async (action: () => Promise<void>): Promise<void> => {
    try {
      await action()
    } catch (cause) {
      const code = (cause as { code?: string }).code ?? 'INTERNAL'
      process.stderr.write(`${code}: ${cause instanceof Error ? cause.message : String(cause)}\n`)
      process.exitCode = 1
    }
  }

  /** Every id argument accepts an explicit id or `all`. */
  const targets = (root: string, argument?: string): string[] =>
    argument === undefined || argument === 'all' ? listClipIds(root) : [argument]

  /** Resolve a tool argument that is either inline JSON or `@path/to/file.json`. */
  const readInput = async (raw: string): Promise<unknown> => {
    const source = raw.startsWith('@') ? await readFile(raw.slice(1), 'utf8') : raw
    try {
      return JSON.parse(source)
    } catch (cause) {
      throw new UsageError(`input is not valid JSON — ${String(cause)}`)
    }
  }

  program
    .command('doctor')
    .description('diagnose every subsystem and print an actionable report')
    .option('--json', 'machine-readable output')
    .action(async () => {
      const report = await doctor()
      say(wantsJson() ? JSON.stringify(report, null, 2) : renderReport(report))
      if (!report.ok) process.exitCode = 1
    })

  program
    .command('clips')
    .description('list every clip with its committed verdict')
    .option('--json', 'machine-readable output')
    .option('--failing', 'only clips whose verdict is not pass')
    .action(async () => {
      await guard(async () => {
        const root = findRepoRoot()
        const clips = await listClips(root)
        const shown = process.argv.includes('--failing')
          ? clips.filter((clip) => clip.verdict !== 'pass')
          : clips
        if (wantsJson()) {
          say(JSON.stringify(shown, null, 2))
          return
        }
        if (shown.length === 0) {
          say('No clips matched.')
          return
        }
        const width = Math.max(...shown.map((clip) => clip.id.length), 4)
        say(`  ${'clip'.padEnd(width)}  frames  verdict  peak Δ   flash/s  title`)
        for (const clip of shown) {
          say(
            `  ${clip.id.padEnd(width)}  ${String(clip.frameCount).padStart(6)}  ` +
              `${clip.verdict.padEnd(7)}  ${(clip.peakDelta / 1000).toFixed(3)}  ` +
              `${String(clip.maxFlashesInWindow).padStart(7)}  ${clip.title}`,
          )
        }
        const passing = shown.filter((clip) => clip.verdict === 'pass').length
        say('')
        say(`  ${shown.length} clip(s), ${passing} passing`)
      })
    })

  program
    .command('render')
    .description('render clips to MP4 and commit their manifests')
    .argument('[clip]', 'clip id, or "all" (default: all)')
    .option('--crf <number>', 'H.264 quality, lower is better', '20')
    .option('--json', 'machine-readable output')
    .action(async (clip: string | undefined, options: { crf?: string }) => {
      await guard(async () => {
        const root = findRepoRoot()
        const ids = targets(root, clip)
        const crf = Number(options.crf ?? '20')
        if (!Number.isFinite(crf) || crf < 0 || crf > 51) {
          throw new Error(`--crf must be between 0 and 51, got ${options.crf}`)
        }
        const results: unknown[] = []
        for (const id of ids) {
          process.stderr.write(`rendering ${id}…\n`)
          const rendered = await renderClipToRepo(root, id, { crf })
          await recordClipRun(root, rendered.manifest, 'render', `${rendered.videoBytes} bytes`)
          results.push({
            id: rendered.id,
            verdict: rendered.verdict,
            frames: rendered.manifest.frameCount,
            bytes: rendered.videoBytes,
            digestsReproduced: rendered.digestsReproduced,
            rootDigest: rendered.manifest.rootDigest,
          })
          process.stderr.write(
            `  ${rendered.verdict === 'pass' ? 'ok  ' : 'FAIL'} ${rendered.id} ` +
              `${rendered.manifest.frameCount} frames, ${(rendered.videoBytes / 1024).toFixed(0)} KB, ` +
              `digests reproduced across both passes\n`,
          )
        }
        if (wantsJson()) {
          say(JSON.stringify(results, null, 2))
          return
        }
        say(`${results.length} clip(s) rendered`)
      })
    })

  program
    .command('audit')
    .description('recompute digests, telemetry and audits without encoding a video')
    .argument('[clip]', 'clip id, or "all" (default: all)')
    .option('--json', 'machine-readable output')
    .action(async (clip: string | undefined) => {
      await guard(async () => {
        const root = findRepoRoot()
        const ids = targets(root, clip)
        const results: {
          id: string
          verdict: string
          failingAudits: string[]
          reasons: string[]
          rootDigest: string
        }[] = []
        for (const id of ids) {
          const manifest = await auditClipToRepo(root, id)
          results.push({
            id,
            verdict: manifest.verdict,
            failingAudits: manifest.failingAudits as string[],
            reasons: manifest['reasons'] as string[],
            rootDigest: manifest.rootDigest,
          })
          const detail =
            manifest.verdict === 'pass'
              ? 'all audits pass'
              : `${manifest.failingAudits.join(', ')} — ${(manifest['reasons'] as string[]).join('; ')}`
          await recordClipRun(root, manifest, 'audit', detail)
          say(`  ${id.padEnd(22)} ${manifest.verdict.padEnd(5)} ${detail}`)
        }
        if (wantsJson()) say(JSON.stringify(results, null, 2))
        const failing = results.filter((result) => result.verdict !== 'pass')
        if (failing.length > 0) process.exitCode = 1
      })
    })

  program
    .command('verify')
    .description('re-render every frame and prove it matches the committed manifest')
    .argument('[clip]', 'clip id, or "all" (default: all)')
    .option('--json', 'machine-readable output')
    .action(async (clip: string | undefined) => {
      await guard(async () => {
        const root = findRepoRoot()
        const bridge = new EngineBridge({
          module: 'framesafe',
          cwd: join(root, 'services', 'engine', 'src'),
          timeoutMs: 20 * 60_000,
        })
        const results: unknown[] = []
        for (const id of targets(root, clip)) {
          const spec = await readSpec(root, id)
          const manifest = await readManifest(root, id)
          if (manifest === null) throw new Error(`clip "${id}" has no manifest to verify against`)
          process.stderr.write(`verifying ${id}…\n`)
          const result = (await bridge.call({
            op: 'verify',
            input: { spec, manifest },
          })) as { reproducible: boolean; firstDifference: { frameIndex: number | null } }
          results.push({ id, ...result })
          const where = result.firstDifference.frameIndex
          say(
            `  ${result.reproducible ? 'ok  ' : 'FAIL'} ${id.padEnd(22)} ` +
              (result.reproducible ? 'every frame digest reproduced' : `diverged at frame ${String(where)}`),
          )
        }
        if (wantsJson()) say(JSON.stringify(results, null, 2))
        const diverged = (results as { reproducible: boolean }[]).filter((r) => !r.reproducible)
        if (diverged.length > 0) process.exitCode = 1
      })
    })

  program
    .command('frame')
    .description('print the digest of one frame')
    .argument('<clip>', 'clip id')
    .argument('<index>', 'frame index')
    .action(async (clip: string, index: string) => {
      await guard(async () => {
        const root = findRepoRoot()
        const spec = await readSpec(root, clip)
        const bridge = new EngineBridge({
          module: 'framesafe',
          cwd: join(root, 'services', 'engine', 'src'),
          timeoutMs: 5 * 60_000,
        })
        const frame = Number(index)
        const result = (await bridge.call({
          op: 'digests',
          input: { spec, from: frame, to: frame + 1 },
        })) as { frames: { i: number; digest: string }[]; renderer: Record<string, string> }
        const entry = result.frames[0]
        if (entry === undefined) throw new Error(`frame ${index} is outside the clip`)
        say(`${clip} frame ${entry.i}: ${entry.digest}`)
        say(
          `renderer: ${Object.entries(result.renderer)
            .map(([k, v]) => `${k}=${v}`)
            .join(' ')}`,
        )
      })
    })

  program
    .command('spec')
    .description('print the compiled plan for a clip: frames, layers, windows, digest')
    .argument('<clip>', 'clip id')
    .option('--json', 'machine-readable output')
    .action(async (clip: string) => {
      await guard(async () => {
        const root = findRepoRoot()
        const bridge = new EngineBridge({
          module: 'framesafe',
          cwd: join(root, 'services', 'engine', 'src'),
        })
        const plan = (await bridge.call({
          op: 'compile',
          input: { spec: await readSpec(root, clip) },
        })) as {
          frameCount: number
          durationS: number
          specDigest: string
          continuityBudget: number
          layers: { index: number; kind: string; name: string; reveal: string; easing: string }[]
        }
        if (wantsJson()) {
          say(JSON.stringify(plan, null, 2))
          return
        }
        say(`${clip}: ${plan.frameCount} frames, ${plan.durationS}s, ${plan.specDigest}`)
        for (const layer of plan.layers) {
          say(
            `  ${String(layer.index).padStart(2)} ${layer.kind.padEnd(10)} ${layer.name.padEnd(14)} ${layer.reveal.padEnd(7)} ${layer.easing}`,
          )
        }
        say(`  continuity budget ${plan.continuityBudget}`)
      })
    })

  program
    .command('index')
    .description('rebuild the local clip index from every committed manifest')
    .option('--json', 'machine-readable output')
    .action(async () => {
      await guard(async () => {
        const root = findRepoRoot()
        const stats = await rebuildIndex(root)
        if (wantsJson()) {
          say(JSON.stringify(stats, null, 2))
          return
        }
        say(
          `indexed ${stats.clips} clip(s) at ${indexPath(root)} — ${stats.passing} passing, ${stats.failing} failing, ${stats.runs} run(s) recorded`,
        )
      })
    })

  program
    .command('runs')
    .description('show recent render and audit runs from the local index')
    .argument('[clip]', 'clip id')
    .option('--limit <number>', 'how many runs to show', '15')
    .option('--json', 'machine-readable output')
    .action(async (clip: string | undefined, options: { limit?: string }) => {
      await guard(async () => {
        const root = findRepoRoot()
        const limit = Number(options.limit ?? '15')
        const runs = await readRuns(root, clip, Number.isFinite(limit) ? limit : 15)
        if (runs === null) {
          say('No index yet — run `framesafe index` first.')
          return
        }
        if (wantsJson()) {
          say(JSON.stringify(runs, null, 2))
          return
        }
        if (runs.length === 0) {
          say('No runs recorded yet.')
          return
        }
        for (const run of runs) {
          const when = new Date(run.created_at).toISOString().replace('T', ' ').slice(0, 19)
          say(`  ${when}  ${run.op.padEnd(6)}  ${run.clip.padEnd(22)} ${run.verdict ?? '-'}`)
        }
      })
    })

  program
    .command('tools')
    .description('list the registered tools — the authoritative capability list')
    .option('--json', 'machine-readable output')
    .action(() => {
      const registry = buildToolRegistry()
      const tools = registry.list().map((tool) => ({
        name: tool.name,
        description: tool.description,
        surface: registry.surfaceOf(tool.name),
        source: registry.sourceOf(tool.name),
        permissions: tool.permissions,
        inputSchema: tool.inputSchema,
      }))
      if (wantsJson()) {
        say(JSON.stringify(tools, null, 2))
        return
      }
      const width = Math.max(...tools.map((tool) => tool.name.length), 4)
      for (const tool of tools) {
        say(`  ${tool.name.padEnd(width)}  [${tool.surface}]  ${tool.description}`)
      }
    })

  program
    .command('skills')
    .description('list the skill catalog')
    .option('--json', 'machine-readable output')
    .action(async () => {
      await guard(async () => {
        const root = findRepoRoot()
        const { loadCatalog } = await import('@framesafe/skills')
        const { skills, issues } = loadCatalog(`${root}/skills`)
        if (wantsJson()) {
          say(
            JSON.stringify(
              {
                count: skills.length,
                issues: [...issues],
                skills: skills.map((skill) => ({
                  name: skill.name,
                  version: skill.version,
                  description: skill.description,
                })),
              },
              null,
              2,
            ),
          )
          return
        }
        for (const skill of skills)
          say(`  ${skill.name.padEnd(22)} ${skill.version.padEnd(8)} ${skill.description}`)
        if (issues.length > 0) {
          say(`  ${issues.length} issue(s):`)
          for (const issue of issues) say(`    ${issue}`)
          process.exitCode = 1
        }
      })
    })

  program
    .command('plugins')
    .description('list the resolved plugin registry and why anything was rejected')
    .option('--json', 'machine-readable output')
    .action(async () => {
      await guard(async () => {
        const root = findRepoRoot()
        const { buildRegistry } = await import('@framesafe/plugins')
        const result = buildRegistry(`${root}/plugins`)
        if (wantsJson()) {
          say(JSON.stringify(result, null, 2))
          return
        }
        for (const plugin of result.active) {
          say(`  active    ${plugin.manifest.name.padEnd(20)} ${plugin.manifest.version}`)
        }
        for (const plugin of result.disabled) {
          say(`  disabled  ${plugin.manifest.name}`)
        }
        for (const plugin of result.rejected) {
          say(`  rejected  ${plugin.path}: ${plugin.issues.join('; ')}`)
        }
      })
    })

  const mcp = program.command('mcp').description('Model Context Protocol commands')

  mcp
    .command('serve')
    .description('run the MCP server over stdio')
    .action(async () => {
      const { serveStdio } = await import('@framesafe/mcp')
      // stdout belongs to the protocol from here on; diagnostics must go to stderr.
      await serveStdio(buildToolRegistry(), createContext('mcp'))
    })

  mcp
    .command('call')
    .description('invoke one tool directly, without MCP')
    .argument('<tool>', 'tool name')
    .argument('<input>', 'JSON input document')
    .action(async (tool: string, raw: string) => {
      let parsed: unknown
      try {
        parsed = await readInput(raw)
      } catch (cause) {
        process.stderr.write(`usage: ${cause instanceof Error ? cause.message : String(cause)}\n`)
        process.exitCode = 2
        return
      }
      try {
        const value = await buildToolRegistry().invokeValidated(tool, parsed, createContext('cli'), [
          'fs:read',
          'fs:write',
          'net:fetch',
          'proc:spawn',
        ])
        say(JSON.stringify(value ?? null, null, 2))
      } catch (cause) {
        const code = (cause as { code?: string }).code ?? 'INTERNAL'
        process.stderr.write(`${code}: ${cause instanceof Error ? cause.message : String(cause)}\n`)
        process.exitCode = 1
      }
    })

  program
    .command('run')
    .description('invoke a tool by name — the same path the MCP server takes')
    .argument('<tool>', 'tool name')
    .argument('<input>', 'JSON input document')
    .action(async (tool: string, raw: string) => {
      let parsed: unknown
      try {
        parsed = await readInput(raw)
      } catch (cause) {
        process.stderr.write(`usage: ${cause instanceof Error ? cause.message : String(cause)}\n`)
        process.exitCode = 2
        return
      }
      try {
        const value = await buildToolRegistry().invokeValidated(tool, parsed, createContext('cli'), [
          'fs:read',
          'fs:write',
          'proc:spawn',
        ])
        say(JSON.stringify(value ?? null, null, 2))
      } catch (cause) {
        const code = (cause as { code?: string }).code ?? 'INTERNAL'
        process.stderr.write(`${code}: ${cause instanceof Error ? cause.message : String(cause)}\n`)
        process.exitCode = 1
      }
    })

  program
    .command('version')
    .description('print version and runtime information as JSON')
    .action(() => {
      say(
        JSON.stringify(
          {
            name: 'framesafe',
            version: VERSION,
            node: process.versions.node,
            platform: process.platform,
            tools: buildToolRegistry().size,
            clips: listClipIds(findRepoRoot()).length,
          },
          null,
          2,
        ),
      )
    })

  return program
}
