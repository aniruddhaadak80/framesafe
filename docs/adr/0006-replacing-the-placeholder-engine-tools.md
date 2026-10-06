# ADR-0006 — Replacing the scaffold's engine tools

**Status:** accepted · **Date:** 2026-10-06

## Context

The repository was generated from a scaffold whose three engine tools were `engine_summarize`,
`engine_diff` and `engine_normalize`: three tools over a generic `records` shape. They worked,
they passed their tests, and they were placeholder behaviour inherited from a different product.

The scaffold's own guidance is "extend, don't replace". Taken literally that would have left a
motion-graphics product whose MCP surface advertised three tools about `records` and none about
clips. A visitor calling `framesafe tools` would have learned nothing true about the product.

## Decision

Keep `list_skills` and `list_plugins`, which are real and still correct. Replace the three
generic engine tools with the eight tools this product actually needs:

| Tool           | Why it must exist                                    |
| -------------- | ---------------------------------------------------- |
| `list_clips`   | discover clip ids and verdicts before anything else  |
| `compile_spec` | check a spec, or read exactly what a clip is made of |
| `audit_clip`   | decide whether a clip is safe to ship                |
| `verify_clip`  | prove the library still renders byte-identically     |
| `frame_digest` | pin down which frame diverged                        |
| `render_clip`  | produce the video and the manifest                   |
| `list_skills`  | retained from the scaffold                           |
| `list_plugins` | retained from the scaffold                           |

## Consequences

- Every advertised tool is something a caller would actually ask for.
- Input validation moved into the registry itself (`ToolRegistry.invokeValidated`), because with
  eight tools and four transports, per-transport validation was already drifting. A schema that
  silently ignores what it declares is refused outright.
- The MCP surface is 8 tools, over the "at least five" contract, and `scripts/prove-mcp.mjs`
  prints the evidence: a real handshake, `tools/list`, two engine-backed calls, and a rejected
  malformed call.
- `packages/sdk` no longer re-exports `channels` or `providers`, because those surfaces do not
  exist (ADR-0005). A facade that re-exports a missing module is a lie about the product.
