# CLI

Every capability is reachable without a browser. The binary is `packages/cli/dist/bin.js` after
`npm run build`; install it globally as `framesafe` if you prefer the short form.

## Exit codes

| Code | Meaning                                                                     |
| ---- | --------------------------------------------------------------------------- |
| `0`  | success                                                                     |
| `1`  | runtime failure — an audit failed, a digest diverged, a subsystem is broken |
| `2`  | usage error — unknown flag, unparseable input                               |

`audit` and `verify` exit `1` on a failing result on purpose: they are meant to be CI checks.

## The library

```bash
framesafe clips              # every clip, with verdict, peak motion, flashes/s
framesafe clips --failing    # only the ones that fail
framesafe clips --json       # the same, machine-readable
```

```
  clip                frames  verdict  peak Δ   flash/s  title
  continuity-breach      120  fail     0.108        0  Continuity breach (intentional fail)
  counter-roll           144  pass     0.007        0  Odometer counter
  flash-strobe           120  fail     0.889        4  Strobe breach (intentional fail)
  ...
  15 clip(s), 12 passing
```

## Inspecting

```bash
framesafe spec easing-lab            # compiled frame table: layers, windows, easing, digest
framesafe frame title-block 96       # the digest of one frame, plus the renderer fingerprint
```

## Auditing and verifying

```bash
framesafe audit all        # re-derive the three audits from stored telemetry (no rendering)
framesafe verify all       # re-render every frame and compare against the committed manifest
```

`verify` is the load-bearing command: it is the difference between a claim and a check.

```
  ok   title-block          every frame digest reproduced
  ok   flash-strobe         every frame digest reproduced
```

## Rendering

```bash
framesafe render orbit-grid             # one clip
framesafe render all                   # the whole library
framesafe render all --crf 18          # smaller files, more artefacts
```

Two engine processes render the frames — one builds the manifest, one streams pixels into the
encoder — and their digests are compared **before** anything is written. If they disagree the
command fails and names the frame: a non-deterministic render is never published.

Encoding uses the `ffmpeg-static` binary from `node_modules`, overridable with `FFMPEG_PATH`.

## Local index

```bash
framesafe index           # rebuild .data/framesafe.db from the manifests
framesafe runs            # recent render and audit runs
framesafe runs title-block
```

The index is a projection of git, not a source of truth (ADR-0005). Deleting `.data` costs
nothing; `framesafe index` rebuilds it.

## Invoking tools

```bash
framesafe tools                       # the registry
framesafe skills                      # the catalog, with issues
framesafe plugins                     # active, disabled, rejected — and why
framesafe run audit_clip @input.json  # the same path the MCP server takes
framesafe mcp serve                   # MCP over stdio
framesafe mcp call list_clips '{}'
```

Input is inline JSON or `@path/to/file.json`. Prefer the file form: shell quoting of JSON is a
solved problem you should not have to solve twice. Input is validated against the tool's schema
first, so a malformed call returns `VALIDATION_FAILED` with the offending field rather than a
stack trace.

## Diagnostics

```bash
framesafe doctor            # every subsystem, with a fix hint per failing row
framesafe doctor --json
framesafe version
```

## Error codes

| Code                | Meaning                                 | First move                     |
| ------------------- | --------------------------------------- | ------------------------------ |
| `VALIDATION_FAILED` | input did not match the tool's schema   | fix the caller                 |
| `PERMISSION_DENIED` | the tool needs a permission not granted | check the declarations         |
| `NOT_FOUND`         | no such clip, skill or plugin           | `framesafe clips`              |
| `CONFLICT`          | duplicate tool name at registration     | find the other registrant      |
| `UPSTREAM_FAILED`   | the engine or the encoder failed        | run the engine op directly     |
| `TIMEOUT`           | the engine exceeded its budget          | `framesafe verify` on one clip |
