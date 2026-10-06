# Architecture

```
clips/<id>/spec.json
        │
        │  validate + canonicalise          services/engine (Python, pure)
        ▼
   ClipPlan  ── progress(layer, frameIndex) is a pure function of the index
        │
        ├──▶ render_frame(n) ──▶ sha256 per frame ──▶ manifests ──▶ audits ──▶ verdict
        │
        └──▶ raw RGB ──▶ ffmpeg (host side) ──▶ apps/web/public/clips/<id>.mp4
                                                          │
                                                   the gallery reads the manifest
```

## The narrow waist

Every capability is a `Tool`. One registry. One interface.

```
                  ┌──────────────────────────────────┐
  CLI ───────────▶│                                  │
  MCP server ────▶│  ToolRegistry.invokeValidated()  │──▶ Python engine (proc:spawn)
                  │  validate → permissions → call   │──▶ clips/*.json        (fs:read)
                  └──────────────────────────────────┘──▶ .data/*.db, *.mp4  (fs:write)
```

The web app does not sit on the waist: it renders committed manifests, because a Vercel function
has neither a filesystem it may depend on nor a business holding verdicts it computed itself. That
is a deliberate asymmetry, and it is why the site's claims are exactly `framesafe audit`'s claims.

Validation lives **inside the registry** rather than in each transport. With eight tools and three
transports, per-transport validation had already drifted once during this build.

## Invariants

1. **Tools are stateless.** State lives in `packages/memory` or in git, never in a tool.
2. **Input is validated before the handler runs**, against the declared `inputSchema`. A schema
   keyword the validator does not implement is an error, not a silent pass.
3. **Permissions are declared, not assumed.** Nothing is granted beyond a tool's own declaration.
4. **Duplicate tool names throw**, naming both registrants.
5. **No cross-package deep imports.** Enforced by `check:boundaries`.
6. **The engine is pure.** No clock, no network, no filesystem, no randomness, no model. Its one
   documented side channel is the `frame <i> <digest>` line the streaming renderer writes to stderr
   while pixels go to stdout.

## The footprint ladder

1. Extend an existing tool
2. Add a CLI command plus a skill
3. Add a service-gated tool
4. Add a plugin
5. Add an MCP server tool
6. Add a new core tool — last resort

Every core tool is paid for in context window on every request. That asymmetry is the whole
reason for the ladder.

## The deterministic engine

`services/engine` is a set of pure functions over JSON. The operations are:

| Op               | Renders? | Purpose                                              |
| ---------------- | -------- | ---------------------------------------------------- |
| `compile`        | no       | spec → frame table, layers, digest                   |
| `digests`        | a range  | per-frame digests                                    |
| `telemetry`      | yes      | per-frame luminance and motion                       |
| `manifest`       | yes      | the committed artefact: digests + telemetry + audits |
| `audit_manifest` | no       | re-run the audits from stored telemetry              |
| `verify`         | yes      | re-render and compare against a manifest             |
| `render_stream`  | yes      | raw RGB to stdout, digests to stderr                 |

`audit_manifest` is the interesting one: it re-derives a verdict without rendering, which is what
makes the cheap gate possible and what lets the site trust a committed number.

Internals: `spec.py` validates and normalises, `easing.py` and `geometry.py` are arithmetic,
`glyphs.py` is the stroke font, `plan.py` compiles windows to progress, `render.py` paints,
`audit.py` measures, `digest.py` addresses.

## Determinism, concretely

| Hidden input that motion graphics normally has | What framesafe does instead                                       |
| ---------------------------------------------- | ----------------------------------------------------------------- |
| system font                                    | stroke font defined in `glyphs.py`                                |
| wall clock                                     | `frameIndex / fps`                                                |
| `Math.random()`                                | fixed LCG seeded from the spec                                    |
| GPU / float rounding                           | Pillow, integer-accurate, version recorded per manifest           |
| ffmpeg build                                   | the encoder is downstream; digests cover the engine's frames only |

Supersampling gives antialiasing without a GPU: draw at 2×, box-filter down. For an integer
factor that is exact area averaging, not an approximation.

## Data model

| Entity                                           | Where                            | Authoritative?                 |
| ------------------------------------------------ | -------------------------------- | ------------------------------ |
| `Clip` (spec)                                    | `clips/<id>/spec.json`           | yes                            |
| `Manifest` (digests, telemetry, audits, verdict) | `clips/<id>/manifest.json`       | yes, as evidence               |
| `Video`                                          | `apps/web/public/clips/<id>.mp4` | derived, but digested          |
| `ClipRow` / `RunRow`                             | `.data/framesafe.db`             | no — a projection, rebuildable |

See [ADR-0004](adr/0004-manifest-is-the-contract.md) and
[ADR-0005](adr/0005-omitted-surfaces-and-state.md).

## Gates that exist because something was wrong

- `check:clip-specs` — found 26 layout defects across 13 clips
- `check:manifests` — re-derives each spec digest with the engine, and checks the video's size
  and digest against the manifest
- `check:readme-commands` — extended to verify `node <path>` and `python <path>` invocations,
  because that is the dominant command shape in this README

See [docs/notes/](notes/).
