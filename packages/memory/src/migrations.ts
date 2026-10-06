/**
 * Migrations are numbered, ordered, and idempotent. Never edit an applied migration —
 * append a new one. `user_version` is the source of truth for the applied prefix.
 */
export interface Migration {
  readonly version: number
  readonly name: string
  readonly up: readonly string[]
}

export const MIGRATIONS: readonly Migration[] = [
  {
    version: 1,
    name: 'initial',
    up: [
      `CREATE TABLE IF NOT EXISTS records (
         id         TEXT PRIMARY KEY,
         kind       TEXT NOT NULL,
         payload    TEXT NOT NULL,
         created_at INTEGER NOT NULL,
         updated_at INTEGER NOT NULL
       )`,
      `CREATE INDEX IF NOT EXISTS records_kind_idx ON records (kind, updated_at DESC)`,
    ],
  },
  {
    version: 2,
    name: 'full_text',
    up: [
      `CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5 (
         id UNINDEXED, body, tokenize = 'porter unicode61'
       )`,
    ],
  },
  {
    version: 3,
    name: 'clips_and_runs',
    up: [
      // The clip index is a *derived* store: every column here is reproducible from
      // clips/<id>/manifest.json, which stays the source of truth. That is what lets the
      // index be rebuilt from scratch at any time without losing anything.
      `CREATE TABLE IF NOT EXISTS clips (
         id            TEXT PRIMARY KEY,
         title         TEXT NOT NULL,
         verdict       TEXT NOT NULL,
         frame_count   INTEGER NOT NULL,
         fps           INTEGER NOT NULL,
         root_digest   TEXT NOT NULL,
         spec_digest   TEXT NOT NULL,
         peak_delta    INTEGER NOT NULL,
         failing_audits TEXT NOT NULL,
         video_bytes   INTEGER NOT NULL,
         manifest_json TEXT NOT NULL,
         updated_at    INTEGER NOT NULL
       )`,
      `CREATE INDEX IF NOT EXISTS clips_verdict_idx ON clips (verdict)`,
      `CREATE TABLE IF NOT EXISTS clip_runs (
         id          INTEGER PRIMARY KEY AUTOINCREMENT,
         clip        TEXT NOT NULL,
         op          TEXT NOT NULL,
         verdict     TEXT,
         detail      TEXT,
         created_at  INTEGER NOT NULL,
         FOREIGN KEY (clip) REFERENCES clips (id) ON DELETE CASCADE
       )`,
      `CREATE INDEX IF NOT EXISTS clip_runs_clip_idx ON clip_runs (clip, created_at DESC)`,
      `CREATE VIRTUAL TABLE IF NOT EXISTS clips_fts USING fts5 (
         id UNINDEXED, body, tokenize = 'porter unicode61'
       )`,
    ],
  },
]

export const LATEST_VERSION = MIGRATIONS[MIGRATIONS.length - 1]?.version ?? 0

export function pendingMigrations(current: number): readonly Migration[] {
  return MIGRATIONS.filter((m) => m.version > current).sort((a, b) => a.version - b.version)
}
