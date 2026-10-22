import { describe, expect, it } from 'vitest'
import { LATEST_VERSION, MIGRATIONS, pendingMigrations } from './migrations.js'

describe('MIGRATIONS', () => {
  it('numbers from one, without gaps', () => {
    // The module's contract: migrations are numbered and ordered, and
    // `user_version` is the source of truth for the applied prefix. A gap
    // would make a version number ambiguous - two databases could claim the
    // same prefix and hold different schemas.
    expect(MIGRATIONS.map((m) => m.version)).toEqual(MIGRATIONS.map((_, index) => index + 1))
  })

  it('is ordered by version', () => {
    const versions = MIGRATIONS.map((m) => m.version)
    expect([...versions].sort((a, b) => a - b)).toEqual(versions)
  })

  it('names every migration uniquely', () => {
    const names = MIGRATIONS.map((m) => m.name)
    expect(new Set(names).size).toBe(names.length)
  })

  it('gives every migration at least one statement', () => {
    for (const migration of MIGRATIONS) {
      expect(migration.up.length, migration.name).toBeGreaterThan(0)
    }
  })

  it('writes idempotent SQL', () => {
    // The module says migrations are idempotent, which is what makes a
    // half-applied migration safe to re-run. Every statement has to say so.
    for (const migration of MIGRATIONS) {
      for (const statement of migration.up) {
        expect(statement, `${migration.name}: ${statement}`).toContain('IF NOT EXISTS')
      }
    }
  })
})

describe('LATEST_VERSION', () => {
  it('is the version of the last migration', () => {
    expect(LATEST_VERSION).toBe(MIGRATIONS[MIGRATIONS.length - 1]?.version)
  })
})

describe('pendingMigrations', () => {
  it('returns everything for an empty database', () => {
    expect(pendingMigrations(0)).toEqual([...MIGRATIONS])
  })

  it('returns only what is newer than the current version', () => {
    expect(pendingMigrations(1).map((m) => m.version)).toEqual([2, 3])
    expect(pendingMigrations(2).map((m) => m.version)).toEqual([3])
  })

  it('returns nothing once the database is current', () => {
    expect(pendingMigrations(LATEST_VERSION)).toEqual([])
  })

  it('never downgrades a database that is ahead of the code', () => {
    expect(pendingMigrations(LATEST_VERSION + 10)).toEqual([])
  })

  it('does not reorder the migration list', () => {
    const before = MIGRATIONS.map((m) => m.version)
    pendingMigrations(0)
    expect(MIGRATIONS.map((m) => m.version)).toEqual(before)
  })
})
