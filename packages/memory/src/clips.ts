import type { Store } from './store.js'

/**
 * The clip index: a queryable projection of the committed manifests.
 *
 * The manifests in git stay authoritative — every column here is reproducible from them,
 * which is why `framesafe index` can rebuild this file from nothing. What the index buys is
 * speed and history: "which clips fail the flash audit" without parsing fifteen JSON
 * documents, and "what happened to this clip last Tuesday" without reading a diff.
 */

export interface ClipRow {
  readonly id: string
  readonly title: string
  readonly verdict: string
  readonly frame_count: number
  readonly fps: number
  readonly root_digest: string
  readonly spec_digest: string
  readonly peak_delta: number
  readonly failing_audits: string
  readonly video_bytes: number
  readonly manifest_json: string
  readonly updated_at: number
}

export interface RunRow {
  readonly id: number
  readonly clip: string
  readonly op: string
  readonly verdict: string | null
  readonly detail: string | null
  readonly created_at: number
}

export interface ClipInput {
  readonly id: string
  readonly title: string
  readonly verdict: string
  readonly frameCount: number
  readonly fps: number
  readonly rootDigest: string
  readonly specDigest: string
  readonly peakDelta: number
  readonly failingAudits: readonly string[]
  readonly videoBytes: number
  readonly manifest: unknown
}

export interface IndexStats {
  readonly clips: number
  readonly passing: number
  readonly failing: number
  readonly runs: number
  readonly schemaVersion: number
}

export class ClipIndex {
  readonly #store: Store

  constructor(store: Store) {
    this.#store = store
  }

  /** Insert or refresh a clip row and its full-text body. */
  upsertClip(clip: ClipInput, now: number): void {
    const manifestJson = JSON.stringify(clip.manifest)
    this.#store.transaction(() => {
      this.#store
        .prepare(
          `INSERT INTO clips (
             id, title, verdict, frame_count, fps, root_digest, spec_digest,
             peak_delta, failing_audits, video_bytes, manifest_json, updated_at
           ) VALUES (
             @id, @title, @verdict, @frameCount, @fps, @rootDigest, @specDigest,
             @peakDelta, @failingAudits, @videoBytes, @manifestJson, @now
           )
           ON CONFLICT(id) DO UPDATE SET
             title = excluded.title,
             verdict = excluded.verdict,
             frame_count = excluded.frame_count,
             fps = excluded.fps,
             root_digest = excluded.root_digest,
             spec_digest = excluded.spec_digest,
             peak_delta = excluded.peak_delta,
             failing_audits = excluded.failing_audits,
             video_bytes = excluded.video_bytes,
             manifest_json = excluded.manifest_json,
             updated_at = excluded.updated_at`,
        )
        .run({
          id: clip.id,
          title: clip.title,
          verdict: clip.verdict,
          frameCount: clip.frameCount,
          fps: clip.fps,
          rootDigest: clip.rootDigest,
          specDigest: clip.specDigest,
          peakDelta: clip.peakDelta,
          failingAudits: clip.failingAudits.join(','),
          videoBytes: clip.videoBytes,
          manifestJson,
          now,
        })
      // FTS5 has no UPSERT: replace the index row explicitly.
      this.#store.prepare('DELETE FROM clips_fts WHERE id = ?').run(clip.id)
      this.#store.prepare('INSERT INTO clips_fts (id, body) VALUES (?, ?)').run(clip.id, manifestJson)
    })
  }

  recordRun(run: { clip: string; op: string; verdict?: string; detail?: string }, now: number): void {
    this.#store.transaction(() => {
      this.#store
        .prepare(
          `INSERT INTO clip_runs (clip, op, verdict, detail, created_at)
           VALUES (@clip, @op, @verdict, @detail, @now)`,
        )
        .run({
          clip: run.clip,
          op: run.op,
          verdict: run.verdict ?? null,
          detail: run.detail ?? null,
          now,
        })
    })
  }

  listClips(verdict?: string): readonly ClipRow[] {
    if (verdict === undefined) {
      return this.#store.prepare('SELECT * FROM clips ORDER BY id').all() as ClipRow[]
    }
    return this.#store.prepare('SELECT * FROM clips WHERE verdict = ? ORDER BY id').all(verdict) as ClipRow[]
  }

  getClip(id: string): ClipRow | undefined {
    return this.#store.prepare('SELECT * FROM clips WHERE id = ?').get(id) as ClipRow | undefined
  }

  search(query: string, limit = 20): readonly { id: string; clip: ClipRow }[] {
    const rows = this.#store
      .prepare(
        `SELECT c.* FROM clips_fts f JOIN clips c ON c.id = f.id
           WHERE clips_fts MATCH ? ORDER BY rank LIMIT ?`,
      )
      .all(query, limit) as ClipRow[]
    return rows.map((row) => ({ id: row.id, clip: row }))
  }

  listRuns(clip?: string, limit = 25): readonly RunRow[] {
    if (clip === undefined) {
      return this.#store
        .prepare('SELECT * FROM clip_runs ORDER BY created_at DESC, id DESC LIMIT ?')
        .all(limit) as RunRow[]
    }
    return this.#store
      .prepare('SELECT * FROM clip_runs WHERE clip = ? ORDER BY created_at DESC, id DESC LIMIT ?')
      .all(clip, limit) as RunRow[]
  }

  /** Replace the whole index from a fresh set of manifests. */
  rebuild(clips: readonly ClipInput[], now: number): IndexStats {
    this.#store.transaction(() => {
      this.#store.prepare('DELETE FROM clips').run()
      this.#store.prepare('DELETE FROM clips_fts').run()
    })
    for (const clip of clips) this.upsertClip(clip, now)
    return this.stats()
  }

  stats(): IndexStats {
    const clips = this.#store.prepare('SELECT COUNT(*) AS n FROM clips').get() as { n: number }
    const passing = this.#store.prepare("SELECT COUNT(*) AS n FROM clips WHERE verdict = 'pass'").get() as {
      n: number
    }
    const runs = this.#store.prepare('SELECT COUNT(*) AS n FROM clip_runs').get() as { n: number }
    return {
      clips: clips.n,
      passing: passing.n,
      failing: clips.n - passing.n,
      runs: runs.n,
      schemaVersion: this.#store.version,
    }
  }
}
