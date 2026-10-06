#!/usr/bin/env node
// Prove the MCP surface against a real client over stdio.
//
//   node scripts/prove-mcp.mjs
//
// This is the evidence that framesafe is usable as a tool provider for other agents: a real
// MCP handshake, the tool list the server advertises, a tool call that reaches the Python
// engine, and an invalid call that comes back as a protocol-level error rather than a
// crash. Run it before claiming the MCP surface works.

import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { McpClient } from '@framesafe/mcp'

const root = process.cwd()
const cli = join(root, 'packages', 'cli', 'dist', 'bin.js')

if (!existsSync(cli)) {
  console.error(`CLI build not found at ${cli} — run \`npm run build\` first`)
  process.exit(1)
}

const client = new McpClient()
await client.connect({
  id: 'framesafe',
  command: process.execPath,
  args: [cli, 'mcp', 'serve'],
  enabled: true,
})

const tools = await client.listTools()
console.log(`tools/list -> ${tools.length} tool(s)`)
for (const tool of tools) {
  console.log(`  ${tool.name.padEnd(14)} ${tool.description.slice(0, 72)}...`)
}

const clips = await client.callTool('list_clips', {})
console.log(`\ntools/call list_clips -> ${clips.count} clip(s)`)
for (const clip of clips.clips.slice(0, 4)) {
  console.log(`  ${clip.id.padEnd(22)} ${clip.verdict}`)
}

const plan = await client.callTool('compile_spec', { clip: 'title-block' })
console.log(`\ntools/call compile_spec -> ${plan.frameCount} frames, ${plan.specDigest.slice(0, 19)}...`)
console.log(`  layers: ${plan.layers.length}`)

const digest = await client.callTool('frame_digest', { clip: 'title-block', frame: 0 })
console.log(
  `\ntools/call frame_digest -> frame ${digest.frames[0].i}: ${digest.frames[0].digest.slice(0, 26)}...`,
)
console.log(`  renderer: ${JSON.stringify(digest.renderer)}`)

let rejected = false
try {
  await client.callTool('frame_digest', { clip: 123 })
} catch (cause) {
  rejected = true
  console.log(`\ntools/call frame_digest (invalid) -> rejected: ${String(cause).split('\n')[0]}`)
}

await client.close()

if (tools.length < 5 || !rejected) {
  console.error('\nMCP proof FAILED: the surface must expose at least five tools and refuse bad input')
  process.exit(1)
}
console.log('\nMCP proof passed')
