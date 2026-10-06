# MCP

framesafe is a tool provider: another agent can compile, audit, verify and render clips without
knowing anything about Pillow, ffmpeg, or frame digests.

```bash
framesafe mcp serve
```

## Proving it works

```bash
node scripts/prove-mcp.mjs
```

That script is a real client over real stdio. It performs the handshake, lists the tools, calls two
of them (one of which reaches the Python engine), and asserts that a malformed call comes back as
an error envelope rather than a crash. Its output is the evidence quoted in the README.

## The tools

| Tool           | Input                    | Returns                                                        |
| -------------- | ------------------------ | -------------------------------------------------------------- |
| `list_clips`   | `{ failingOnly? }`       | every clip with verdict, frame count, peak motion, root digest |
| `compile_spec` | `{ clip }` or `{ spec }` | the compiled frame table and spec digest                       |
| `audit_clip`   | `{ clip }`               | the three audits with measured numbers and reasons             |
| `verify_clip`  | `{ clip }`               | whether every frame digest reproduced, and where it diverged   |
| `frame_digest` | `{ clip, frame }`        | one frame's digest and the renderer fingerprint                |
| `render_clip`  | `{ clip, crf? }`         | video size and digest, root digest, verdict                    |
| `list_skills`  | `{ includeBodies? }`     | the skill catalog                                              |
| `list_plugins` | `{}`                     | the resolved registry, with rejections and reasons             |

Descriptions are written for a model: what the tool does, when to reach for it, and what comes
back. `list_clips` is the discovery entry point — an agent should not have to guess clip ids.

## Names and schemas

Tool names match `^[a-z][a-z0-9_]{0,63}$`, asserted at construction time by
`packages/mcp/src/descriptors.ts`. A name MCP cannot carry fails loudly when the server starts
rather than silently disappearing from the list.

Every `inputSchema` is the tool's real schema, validated by `validateInput` **inside the
registry**, so a client cannot pass an undeclared field and a handler never sees an unvalidated
shape. An unsupported schema keyword is refused: a schema that silently does nothing is worse
than no schema.

## Failure is a value

A tool failure returns an MCP error content block with the product's stable code:

```
VALIDATION_FAILED: input.clip must be string, got number
```

Not a stack trace, not a truncated JSON document. An agent can branch on that code.

## Permissions

The server grants the **union of what the registered tools declare**, and nothing more — a tool
can never reach a capability it did not declare. Tighten it for a specific deployment with
`PRODUCT_MCP_PERMISSIONS=fs:read,proc:spawn`.

`render_clip` declares `fs:write` because it writes a manifest and a video. If your deployment
should not be able to write, omit `fs:write` from the granted set and that tool will refuse.

## Using it as a client

```ts
import { McpClient } from '@framesafe/sdk'

const client = new McpClient()
await client.connect({
  id: 'framesafe',
  command: 'node',
  args: ['/path/to/framesafe/packages/cli/dist/bin.js', 'mcp', 'serve'],
  enabled: true,
})

const clips = await client.callTool('list_clips', {})
console.log(clips.count)
await client.close()
```

`SanitisedEnv` exists because `process.env` is `Record<string, string | undefined>` while the
transport wants only strings — dropping `undefined` there is the difference between a type error
under `exactOptionalPropertyTypes` and a spawn failure at runtime.
