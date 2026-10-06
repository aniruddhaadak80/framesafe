import { readFileSync } from 'node:fs'
import { join } from 'node:path'

/**
 * The product's identity, and the surfaces that actually ship.
 *
 * `status` is not a wish list: every entry here has working code behind it, and the README
 * states the same list with the reason each omission was a decision.
 */

export interface Surface {
  readonly id: string
  readonly title: string
  readonly summary: string
  readonly status: 'shipped' | 'omitted'
  readonly why?: string
}

export const PRODUCT = {
  name: 'framesafe',
  slug: 'framesafe',
  version: '0.1.0',
  tagline:
    'A deterministic motion-graphics compiler: every frame rendered from a spec, addressed by SHA-256, audited for flash safety and continuity, and playable in a gallery.',
} as const

export const SURFACES: readonly Surface[] = [
  {
    id: 'engine',
    title: 'Python deterministic engine',
    summary:
      'Compiles a spec, renders every frame, and computes the digests and audits. No clock, no network, no model call.',
    status: 'shipped',
  },
  {
    id: 'cli',
    title: 'CLI',
    summary:
      'clips, render, audit, verify, frame, spec, index, runs, doctor, tools, mcp. Every capability without a browser.',
    status: 'shipped',
  },
  {
    id: 'web',
    title: 'Web gallery',
    summary:
      'This app. Statically generated from the committed manifests, with a scrubbable frame rail under every clip.',
    status: 'shipped',
  },
  {
    id: 'mcp',
    title: 'MCP server and client',
    summary:
      'Eight tools over stdio, validated at the boundary, so another agent can render and audit clips.',
    status: 'shipped',
  },
  {
    id: 'skills',
    title: 'Skills catalog',
    summary: 'Five skills loaded from disk, with frontmatter validation and a version gate.',
    status: 'shipped',
  },
  {
    id: 'plugins',
    title: 'Plugin registry',
    summary: 'Manifest-driven plugins with priority-based conflict resolution and reported rejections.',
    status: 'shipped',
  },
  {
    id: 'memory',
    title: 'Memory',
    summary: 'SQLite index of clips and runs, rebuildable from the manifests at any time.',
    status: 'shipped',
  },
  {
    id: 'desktop',
    title: 'Desktop shell',
    summary: 'An Electron wrapper around a web gallery adds packaging, not review.',
    status: 'omitted',
    why: 'The gallery is a website and the work happens in a terminal; a shell would distribute the same pixels.',
  },
  {
    id: 'channels',
    title: 'Channels',
    summary: 'A verdict delivered in chat is a verdict nobody can audit.',
    status: 'omitted',
    why: 'Verdicts belong in a committed manifest where they can be diffed and re-derived.',
  },
  {
    id: 'providers',
    title: 'Model providers',
    summary: 'The credibility of this product is a proof, so there is no model tier at any confidence.',
    status: 'omitted',
    why: 'Deliberate: nothing in the render or the audit path calls a model.',
  },
]

export function resolveVersion(): string {
  try {
    const raw = readFileSync(join(process.cwd(), 'package.json'), 'utf8')
    const parsed = JSON.parse(raw) as { version?: string }
    return parsed.version ?? '0.0.0'
  } catch {
    try {
      const raw = readFileSync(join(process.cwd(), '..', '..', 'package.json'), 'utf8')
      const parsed = JSON.parse(raw) as { version?: string }
      return parsed.version ?? '0.0.0'
    } catch {
      return '0.0.0'
    }
  }
}
