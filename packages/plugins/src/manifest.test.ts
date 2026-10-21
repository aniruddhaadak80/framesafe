import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { loadPlugin, loadPlugins } from './manifest.js'

const dirs: string[] = []

afterEach(() => {
  for (const dir of dirs.splice(0)) {
    rmSync(dir, { recursive: true, force: true })
  }
})

/** Write a manifest into a fresh temporary directory and return its path. */
function manifestFile(contents: unknown, name = 'plugin.json'): string {
  const root = mkdtempSync(join(tmpdir(), 'plugins-'))
  dirs.push(root)
  const file = join(root, name)
  writeFileSync(file, typeof contents === 'string' ? contents : JSON.stringify(contents), 'utf8')
  return file
}

const valid = {
  name: 'tariff-lookup',
  version: '1.0.0',
  description: 'Looks up a tariff for a given delivery corridor.',
}

describe('loadPlugin', () => {
  it('reads a valid manifest', () => {
    const loaded = loadPlugin(manifestFile(valid))
    expect(loaded.issues).toEqual([])
    expect(loaded.manifest.name).toBe('tariff-lookup')
    expect(loaded.manifest.version).toBe('1.0.0')
  })

  it('fills in the optional fields', () => {
    const loaded = loadPlugin(manifestFile(valid))
    expect(loaded.manifest.enabled).toBe(true)
    expect(loaded.manifest.priority).toBe(50)
    expect(loaded.manifest.capabilities).toEqual([])
    expect(loaded.manifest.engines).toEqual({})
  })

  it('keeps the values it is given', () => {
    const loaded = loadPlugin(
      manifestFile({
        ...valid,
        enabled: false,
        priority: 10,
        capabilities: ['lookup'],
        engines: { node: '>=22' },
      }),
    )
    expect(loaded.issues).toEqual([])
    expect(loaded.manifest.enabled).toBe(false)
    expect(loaded.manifest.priority).toBe(10)
    expect(loaded.manifest.capabilities).toEqual(['lookup'])
    expect(loaded.manifest.engines).toEqual({ node: '>=22' })
  })

  it('reports a file that is not there', () => {
    const loaded = loadPlugin(join(tmpdir(), 'does-not-exist', 'plugin.json'))
    expect(loaded.manifest).toBeNull()
    expect(loaded.issues).toHaveLength(1)
    expect(loaded.issues[0]).toContain('not found')
  })

  it('reports a file that is not JSON', () => {
    const loaded = loadPlugin(manifestFile('{ not json'))
    expect(loaded.manifest).toBeNull()
    expect(loaded.issues).toHaveLength(1)
    expect(loaded.issues[0]).toContain('invalid JSON')
  })

  it('names the field that broke', () => {
    const loaded = loadPlugin(manifestFile({ ...valid, name: 'Not Kebab' }))
    expect(loaded.manifest).toBeNull()
    expect(loaded.issues).toHaveLength(1)
    expect(loaded.issues[0]).toContain('name')
  })

  it('rejects a version that is not semver', () => {
    const loaded = loadPlugin(manifestFile({ ...valid, version: '1.0' }))
    expect(loaded.issues).toHaveLength(1)
    expect(loaded.issues[0]).toContain('version')
  })

  it('rejects a description that says nothing', () => {
    const loaded = loadPlugin(manifestFile({ ...valid, description: 'short' }))
    expect(loaded.issues).toHaveLength(1)
    expect(loaded.issues[0]).toContain('description')
  })

  it('rejects a priority outside 0..100', () => {
    const loaded = loadPlugin(manifestFile({ ...valid, priority: 101 }))
    expect(loaded.issues).toHaveLength(1)
    expect(loaded.issues[0]).toContain('priority')
  })

  it('reports every broken field at once', () => {
    const loaded = loadPlugin(manifestFile({ name: 'Bad Name', version: '1.0', description: 'short' }))
    expect(loaded.issues).toHaveLength(3)
  })

  it('keeps the path it was given', () => {
    const file = manifestFile(valid)
    expect(loadPlugin(file).path).toBe(file)
  })
})

describe('loadPlugins', () => {
  it('returns nothing when the plugin root does not exist', () => {
    expect(loadPlugins(join(tmpdir(), 'no-such-plugin-root'))).toEqual([])
  })

  it('loads the plugins in a directory', () => {
    const root = mkdtempSync(join(tmpdir(), 'plugins-'))
    dirs.push(root)
    mkdirSync(join(root, 'tariff-lookup'), { recursive: true })
    writeFileSync(join(root, 'tariff-lookup', 'plugin.json'), JSON.stringify(valid), 'utf8')

    const loaded = loadPlugins(root)
    expect(loaded).toHaveLength(1)
    expect(loaded[0]?.manifest.name).toBe('tariff-lookup')
  })

  it('skips a directory that has no manifest', () => {
    const root = mkdtempSync(join(tmpdir(), 'plugins-'))
    dirs.push(root)
    mkdirSync(join(root, 'not-a-plugin'), { recursive: true })

    expect(loadPlugins(root)).toEqual([])
  })
})
