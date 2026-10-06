import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import Link from 'next/link'
import { ClipPlayer } from '@/components/clip-player'
import { allClips, clipById, shortDigest } from '@/lib/clips'

/** The per-clip inspector: the timeline, the audits, and the digests, side by side. */

export const dynamic = 'force-static'

export function generateStaticParams() {
  return allClips().map((clip) => ({ id: clip.id }))
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params
  const clip = clipById(id)
  return clip === undefined
    ? { title: 'Clip not found' }
    : { title: `${clip.title} — framesafe`, description: clip.summary }
}

export default async function ClipPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const clip = clipById(id)
  if (clip === undefined) notFound()

  const audits = Object.entries(clip.audits)
  const holdFrame = clip.reducedMotion.holdFrame

  return (
    <>
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link href="/">← Gallery</Link>
      </nav>

      <header className="clip-head">
        <div className="clip-titles">
          <h1 className="clip-title">{clip.title}</h1>
          <p className="clip-id mono">{clip.id}</p>
        </div>
        <div className="clip-badges">
          <span className="badge" data-tone={clip.verdict === 'pass' ? 'ok' : 'danger'}>
            {clip.verdict}
          </span>
          {clip.intentionalFail ? (
            <span className="badge" data-tone="warn">
              intentional fail
            </span>
          ) : null}
          <span className="badge" data-tone="info">
            {clip.digestsReproducedAcrossPasses ? 'digests reproduced' : 'digests unproven'}
          </span>
        </div>
      </header>

      <p className="clip-summary">{clip.summary}</p>

      <ClipPlayer clip={clip} />

      <section aria-labelledby="audits-heading">
        <h2 id="audits-heading">Audits</h2>
        <div className="audit-list">
          {audits.map(([name, audit]) => (
            <article className="audit" key={name} data-passed={audit.passed}>
              <div className="audit-head">
                <h3>{name}</h3>
                <span className="badge" data-tone={audit.passed ? 'ok' : 'danger'}>
                  {audit.passed ? 'pass' : 'fail'}
                </span>
              </div>
              <p>{audit.reason}</p>
              <dl className="kv">
                {audit.budget !== undefined ? (
                  <>
                    <dt>budget</dt>
                    <dd className="mono">{audit.budget.toFixed(3)}</dd>
                  </>
                ) : null}
                {audit.peakDelta !== undefined ? (
                  <>
                    <dt>peak motion</dt>
                    <dd className="mono">{audit.peakDelta.toFixed(4)}</dd>
                  </>
                ) : null}
                {audit.peakFrame !== undefined ? (
                  <>
                    <dt>peak frame</dt>
                    <dd className="mono">{audit.peakFrame}</dd>
                  </>
                ) : null}
                {audit.maxFlashesInWindow !== undefined ? (
                  <>
                    <dt>flashes / s</dt>
                    <dd className="mono">{audit.maxFlashesInWindow}</dd>
                  </>
                ) : null}
                {audit.range !== undefined ? (
                  <>
                    <dt>luma range</dt>
                    <dd className="mono">{audit.range.toFixed(4)}</dd>
                  </>
                ) : null}
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="timeline-heading">
        <h2 id="timeline-heading">Timeline</h2>
        <dl className="kv kv--wide">
          <dt>frames</dt>
          <dd className="mono">
            {clip.frameCount} at {clip.fps} fps
          </dd>
          <dt>duration</dt>
          <dd className="mono">{(clip.durationMs / 1000).toFixed(2)}s</dd>
          <dt>continuity budget</dt>
          <dd className="mono">{clip.continuityBudget}</dd>
          <dt>contrast ceiling</dt>
          <dd className="mono">{clip.maxAdjacentContrast}</dd>
          <dt>reduced-motion hold</dt>
          <dd className="mono">frame {holdFrame}</dd>
          <dt>renderer</dt>
          <dd className="mono">
            pillow {clip.renderer['pillow'] ?? '?'} · numpy {clip.renderer['numpy'] ?? '?'}
          </dd>
          <dt>spec digest</dt>
          <dd className="mono">{shortDigest(clip.specDigest)}</dd>
          <dt>root digest</dt>
          <dd className="mono">{shortDigest(clip.rootDigest)}</dd>
          {clip.video ? (
            <>
              <dt>video</dt>
              <dd className="mono">
                {clip.video.file} · {(clip.video.bytes / 1024).toFixed(0)} KB · {clip.video.encoder}
              </dd>
            </>
          ) : null}
        </dl>
        {clip.reducedMotion.note ? (
          <p className="note">
            <strong>Reduced motion:</strong> {clip.reducedMotion.note}
          </p>
        ) : null}
      </section>

      <section aria-labelledby="digests-heading">
        <h2 id="digests-heading">Frame digests</h2>
        <p className="muted">
          One SHA-256 per frame, over the canonical RGB bytes at {clip.width}×{clip.height}. The root digest
          folds them in frame order, so a dropped or reordered frame changes it even when every individual
          frame is unchanged.
        </p>
        <ol className="digest-list">
          {clip.frames.slice(0, 8).map((frame) => (
            <li key={frame.i} className="mono">
              {String(frame.i).padStart(3, '0')} · {shortDigest(frame.digest)}
            </li>
          ))}
          {clip.frames.length > 16 ? <li className="muted">… {clip.frames.length - 16} more …</li> : null}
          {clip.frames.length > 8 ? (
            <>
              {clip.frames.slice(-8).map((frame) => (
                <li key={frame.i} className="mono">
                  {String(frame.i).padStart(3, '0')} · {shortDigest(frame.digest)}
                </li>
              ))}
            </>
          ) : null}
        </ol>
      </section>
    </>
  )
}
