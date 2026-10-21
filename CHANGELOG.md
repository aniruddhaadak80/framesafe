# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The Python test job caches pip downloads, so the engine's test dependencies are not
  re-downloaded on every run.
- The clip library: 15 rendered motion-graphics clips, each authored as a declarative spec and
  committed with a manifest carrying a SHA-256 per frame.
- The Python engine: spec validation and normalisation, 14 easing curves, a stroke font defined
  in source, geometry helpers, the frame painter, three audits (flash, continuity, luminance),
  frame and root digests, and a streaming render mode.
- Three audits with measured numbers and reason sentences: flash reversals per second against the
  WCAG 2.3.1 limit, inter-frame motion against each clip's declared `continuityBudget`, and the
  luminance envelope against `maxAdjacentContrast`.
- CLI: `clips`, `spec`, `audit`, `verify`, `render`, `frame`, `index`, `runs`, `run`, `skills`,
  `plugins`, `doctor`, `tools`, `version`, plus `@file.json` input for tool calls.
- The gallery: a single-column web app with a scrubbable frame rail per clip that draws the
  manifest's own telemetry, 15 statically generated clip pages, and `/api/health` that reports
  real probes including whether every clip's digests were reproduced.
- Eight tools over MCP, validated inside the registry, with `scripts/prove-mcp.mjs` as the proof.
- Five skills: `product-overview`, `diagnose`, `author-a-clip`, `read-a-verdict`, `publish-a-clip`.
- A second plugin, `flash-strict`, tightening the flash ceiling for review passes.
- Gates: `check:clip-specs` (compiles every spec, measures text layout) and `check:manifests`
  (re-derives each spec digest with the engine and checks the video against the manifest).

### Fixed

- Every Vercel deployment failed with `MISSING_SERVICES`. The project builds in services mode,
  so the service map lives in the root `vercel.json`, and that file was never committed: no
  branch, production or preview, could build. The map is versioned now, and the new
  `check:vercel-services` gate fails the build if it goes missing again.
- `ClipPlan.out_progress` returned the eased exit curve instead of the remaining share, so every
  layer vanished on the first frame of its exit. Found by the continuity audit on a real clip;
  see `docs/notes/the-audit-caught-the-engine.md`.
- Polygon layers with explicit `points` were not scaled by the supersample factor, drawing at half
  size on a 2× canvas.
- The grid sweep reveal saturated the whole grid to one flat brightness and stopped being a sweep.
- `text_width` was multiplied by the supersample factor twice, so centred text was positioned
  against double its real width.
- The engine validator had no entry for the `background` layer kind and rejected every clip.

### Removed

- The scaffold's generic `engine_summarize`, `engine_diff` and `engine_normalize` tools, replaced
  by the motion tools (ADR-0006).
- Desktop, channels and model providers, with reasons recorded in ADR-0005.

## [0.1.0] - 2026-01-01

### Added

- The narrow waist: one `Tool` interface and one `ToolRegistry`, reachable from the CLI, the web
  app, and the MCP server.
- `framesafe doctor` — subsystem probes with a fix hint per failing row.
- The deterministic Python engine, called as a pure function over stdin/stdout.
- The skills catalog with frontmatter validation and a CI version gate.
- The plugin registry with schema validation and priority-based conflict resolution.
- SQLite storage with WAL, numbered migrations, and FTS5 search.
- An MCP server exposing the registry over stdio, plus an MCP client.
- The web workspace, deployed to Vercel, with a real `/api/health` endpoint.

[Unreleased]: https://github.com/aniruddhaadak80/framesafe/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aniruddhaadak80/framesafe/releases/tag/v0.1.0