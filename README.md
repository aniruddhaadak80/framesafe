<div align="center">

# framesafe

**A deterministic motion-graphics compiler, and the gallery of everything it renders.**

Every frame in this repository is rendered from a declarative spec, addressed by SHA-256,
audited for flash safety and inter-frame continuity, and playable on the web. The library
re-renders byte-identically on any machine.

[CI](https://github.com/aniruddhaadak80/framesafe/actions/workflows/ci.yml) ·
[License](https://github.com/aniruddhaadak80/framesafe/blob/main/LICENSE) ·
[Issues](https://github.com/aniruddhaadak80/framesafe/issues)

</div>

---

## What this is

A clip here is **a JSON document describing timings**, not a video file. `framesafe` compiles
that document into a frame table, renders every frame itself, and commits a manifest
containing a digest per frame plus the result of three audits. Two consequences fall out of
that, and they are the whole product:

1. **The render is reproducible.** Frame _N_ is a pure function of the spec, so a manifest
   committed on one machine is verifiable on another. There is no system font, no GPU, no
   clock, and no RNG in the render path — the type is a stroke font defined in the engine
   source, and all randomness is a seeded generator carried in the spec.
2. **Motion quality becomes arithmetic.** Flash safety (WCAG 2.3.1 / BT.2020), continuity
   against a declared per-clip budget, and the luminance envelope are computed from the
   rendered frames, so "this transition is too abrupt" is a number with a frame index, not an
   opinion.

The credibility claim is a proof, so the engine is code and never a model call.

## Quick start

```bash
git clone https://github.com/aniruddhaadak80/framesafe.git
cd framesafe
npm install
npm run build
node packages/cli/dist/bin.js doctor
```

`doctor` probes the runtime, the skill catalog, the plugin registry and the clip library, and
prints a **fix hint** for anything that fails. Python 3.11+ and `pip install pillow numpy`
are required for the engine.

## Walkthrough

### 1. Look at the library and its verdicts

```bash
node packages/cli/dist/bin.js clips
```

Fifteen clips, each with its frame count, verdict, peak inter-frame motion and flash count.
Two of them fail on purpose — see step 7.

### 2. Compile a spec into a frame table

```bash
node packages/cli/dist/bin.js spec easing-lab
```

Every layer with its window and easing, plus the spec digest. `compile` renders nothing: it is
the pure part of the pipeline.

### 3. Audit a clip's motion

```bash
node packages/cli/dist/bin.js audit flash-strobe
```

```
flash-strobe            fail  flash — 4 flash reversals inside frames 3-27 (limit 3)
```

The reason sentence names the frames and the measured value. `framesafe audit` exits non-zero
when a clip fails, so it works as a CI check.

### 4. Prove the render is reproducible

```bash
node packages/cli/dist/bin.js verify all
```

Re-renders every frame of every clip in a fresh engine process and compares digests against the
committed manifests. This is the command that makes the rest of the repository's claims checkable.

### 5. Render a clip yourself

```bash
node packages/cli/dist/bin.js render morph-blob
```

Two independent engine processes render the frames — one to build the manifest, one to stream
pixels into the encoder — and their digests are compared before anything is written. A clip
whose two passes disagree is refused rather than published.

### 6. Look at one frame without encoding a video

```bash
python scripts/preview-frame.py clips/ring-pulse/spec.json 72 .preview.png
```

### 7. See the negative tests

```bash
node packages/cli/dist/bin.js clips --failing
```

`flash-strobe` exceeds the three-flashes-per-second rule and `continuity-breach` blows its
declared continuity budget on a hard cut. They ship with failing verdicts because an audit that
has never rejected anything is an audit nobody has tested.

### 8. Use it from another agent

```bash
node scripts/prove-mcp.mjs
```

A real MCP client connects over stdio, lists the eight tools, calls two of them (one reaching the
Python engine), and gets a `VALIDATION_FAILED` envelope back for a malformed call.

## The gallery

`apps/web` is the deployed site: a single-column gallery where every clip is playable and carries
its own **frame rail** — one column per frame, drawn from the manifest's telemetry, showing mean
luminance as bar height, inter-frame motion as a step line, and every flash reversal as a red
tick. Scrubbing the rail seeks the video, so the measurement and the thing measured are one
gesture. The pages are statically generated from the committed manifests, so the site needs no
database and cannot disagree with `framesafe audit`.

## Architecture

```
clips/<id>/spec.json ──▶ engine (Python, pure) ──▶ clips/<id>/manifest.json
                              │                            │
                              └─ raw RGB ─▶ ffmpeg ─▶ apps/web/public/clips/<id>.mp4
                                                           │
                                                     the gallery reads the manifest
```

- **The engine** (`services/engine`) is a pure function over JSON on stdin/stdout: no clock, no
  network, no filesystem, no model. See [ADR-0002](docs/adr/0002-python-engine-boundary.md).
- **The manifest is the contract.** Digests, telemetry, audits, verdict. Everything the site shows
  comes from it. See [ADR-0004](docs/adr/0004-manifest-is-the-contract.md).
- **The narrow waist** is one `Tool` registry in `packages/core`. The CLI, the MCP server and the
  site are transports; none of them re-implements a capability. Validation happens in the registry,
  so the shapes cannot drift. See [ADR-0001](docs/adr/0001-narrow-waist.md).
- **Footprint ladder:** extend an existing tool → CLI command + skill → service-gated tool →
  plugin → MCP tool → new core tool. Core is last.

### What ships, and what does not

| Surface             | Status  | Why                                                             |
| ------------------- | ------- | --------------------------------------------------------------- |
| Python engine       | shipped | the credibility of the product                                  |
| CLI                 | shipped | every capability without a browser                              |
| Web gallery         | shipped | the clips, with their evidence                                  |
| MCP server + client | shipped | the product is a tool provider for other agents                 |
| Skills catalog      | shipped | five skills, version-gated                                      |
| Plugin registry     | shipped | `sample` and `flash-strict`                                     |
| Memory              | shipped | SQLite index of clips and runs, rebuildable from the manifests  |
| Desktop shell       | omitted | an Electron wrapper around a website adds packaging, not review |
| Channels            | omitted | a verdict delivered in chat is a verdict nobody can audit       |
| Model providers     | omitted | the credibility claim is a proof, so there is no model tier     |

## CLI reference

| Command                        | What it does                                               |
| ------------------------------ | ---------------------------------------------------------- |
| `clips [--failing]`            | every clip with its committed verdict                      |
| `spec <id>`                    | the compiled frame table for a clip                        |
| `audit [id\|all]`              | re-run the three audits from telemetry; exits 1 on failure |
| `verify [id\|all]`             | re-render and compare against the committed digests        |
| `render [id\|all]`             | render MP4s and write manifests                            |
| `frame <id> <n>`               | the digest of a single frame                               |
| `index`                        | rebuild the local SQLite index                             |
| `runs [id]`                    | recent render and audit runs                               |
| `doctor`                       | probe every subsystem with a fix hint                      |
| `tools` / `skills` / `plugins` | the registry, the catalog, and why anything was rejected   |
| `run <tool> [@file.json]`      | invoke a tool through the same path the MCP server takes   |
| `mcp serve` / `mcp call`       | run or call the MCP server                                 |

`@file.json` exists because shell quoting of JSON is a solved problem you should not have to solve.

## Quality gates

`npm run check` runs all of it: format, lint, typecheck (TypeScript **and** `mypy --strict`),
policy gates, `pytest`, `vitest`, and the Next build.

Two gates exist because of things this build actually got wrong:

- `npm run check:clip-specs` compiles every spec, checks that each text layer stays inside the
  safe inset, and fails on overlapping text. It found 26 layout defects across 13 clips.
- `npm run check:manifests` re-derives each spec digest **with the engine's own compiler** and
  checks the manifest against its own frames and its own video file.

## Development

```bash
npm run dev            # web app + watch builds
npm test               # TypeScript
npm run pytest         # Python engine, including property and golden tests
npm run check          # everything CI runs
npm run format         # prettier
```

Python gates run standalone too: `python -m ruff check services/engine` and
`python -m mypy services/engine/src`.

## Docs

| Document                                         | What it covers                                          |
| ------------------------------------------------ | ------------------------------------------------------- |
| [docs/clip-authoring.md](docs/clip-authoring.md) | the spec schema, every layer kind and reveal mode       |
| [docs/architecture.md](docs/architecture.md)     | the narrow waist, the data model, the footprint ladder  |
| [docs/cli.md](docs/cli.md)                       | every command and its exit codes                        |
| [docs/mcp.md](docs/mcp.md)                       | the eight tools and how another agent uses them         |
| [docs/gallery.md](docs/gallery.md)               | the site, the frame rail, and the design tokens         |
| [docs/ci.md](docs/ci.md)                         | jobs, gates and ratchets                                |
| [docs/notes/](docs/notes/)                       | engineering notes written next to real changes          |
| [docs/adr/](docs/adr/)                           | the decisions, with the alternatives that were rejected |

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [skills/AGENTS.md](skills/AGENTS.md). If you are adding
a clip, `skills/author-a-clip/SKILL.md` is the shortest correct route.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
