#!/usr/bin/env node
// The Vercel project builds in services mode, so the service map lives in the root
// `vercel.json`. If that file is missing, unparseable, or declares no service, every
// deployment dies with MISSING_SERVICES before a build starts - and no GitHub Actions
// job sees it, because the failure happens on Vercel's side.

import { readFileSync, statSync } from 'node:fs'
import { join, posix, relative, sep } from 'node:path'

const ROOT = process.cwd()
const VERCEL_JSON = join(ROOT, 'vercel.json')

function fail(message, fix) {
  console.error(`check:vercel-services FAILED — ${message}`)
  if (fix) console.error(`  fix: ${fix}`)
  process.exit(1)
}

function exists(path) {
  try {
    statSync(path)
    return true
  } catch {
    return false
  }
}

// Turns a workspace glob such as "packages/*" into an anchored regular expression.
function globToRegExp(pattern) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`^${escaped.replace(/\*/g, '[^/]+')}$`)
}

let raw
try {
  raw = readFileSync(VERCEL_JSON, 'utf8')
} catch {
  fail(
    'vercel.json is missing',
    'the Vercel project builds in services mode and needs the service map committed at the repository root',
  )
}

let config
try {
  config = JSON.parse(raw)
} catch (error) {
  fail(`vercel.json is not valid JSON (${error.message})`, 'fix the JSON syntax')
}

const services = config.services
if (!services || typeof services !== 'object' || Array.isArray(services)) {
  fail(
    'vercel.json declares no "services" map',
    'add a "services" object with at least one service, each with a "root"',
  )
}

const names = Object.keys(services)
if (names.length === 0) {
  fail('vercel.json declares an empty "services" map', 'declare at least one service')
}

const workspaces = []
try {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'))
  for (const pattern of pkg.workspaces ?? []) workspaces.push(globToRegExp(pattern))
} catch {
  fail('the root package.json could not be read', 'the service roots are resolved against the workspace list')
}

for (const name of names) {
  const service = services[name]
  if (!service || typeof service !== 'object') {
    fail(`service "${name}" is not an object`, 'each service needs at least a "root"')
  }
  if (typeof service.root !== 'string' || service.root.length === 0) {
    fail(
      `service "${name}" has no "root"`,
      'the root is the directory Vercel builds, relative to the repository root',
    )
  }

  const serviceRoot = service.root.replace(/\\/g, '/').replace(/^\.\//, '').replace(/\/$/, '')
  const rootPath = join(ROOT, ...serviceRoot.split('/'))

  if (!exists(rootPath)) {
    fail(
      `service "${name}" points at "${service.root}", which does not exist`,
      'the service root is the directory Vercel builds',
    )
  }
  if (!exists(join(rootPath, 'package.json'))) {
    fail(
      `service "${name}" points at "${service.root}", which has no package.json`,
      'a service root must be a package so the install and build commands have something to resolve',
    )
  }
  if (workspaces.length > 0 && !workspaces.some((pattern) => pattern.test(serviceRoot))) {
    fail(
      `service "${name}" points at "${service.root}", which no workspace in package.json covers`,
      'add the service root to the "workspaces" list so npm ci and --workspace resolve it',
    )
  }

  const rel = relative(ROOT, rootPath).split(sep).join('/')
  console.log(`check:vercel-services — service "${name}" builds ${posix.normalize(rel)}`)
}

console.log(`check:vercel-services — clean (${names.join(', ')})`)
