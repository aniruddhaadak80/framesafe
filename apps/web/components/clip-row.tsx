import Link from 'next/link'
import type { Clip } from '@/lib/clips'
import { shortDigest } from '@/lib/clips'
import { ClipPlayer } from './clip-player'

/**
 * The gallery row for one clip.
 *
 * The verdict badge comes straight from the committed manifest, including the deliberate
 * negative tests: a failing clip is shown as failing, labelled as intentional, rather than
 * hidden or re-styled to look safe.
 */

export function ClipRow({ clip }: { readonly clip: Clip }) {
  const failing = clip.verdict !== 'pass'
  return (
    <article className="clip" id={clip.id}>
      <header className="clip-head">
        <div className="clip-titles">
          <h3 className="clip-title">
            <Link href={`/clips/${clip.id}`}>{clip.title}</Link>
          </h3>
          <p className="clip-id mono">{clip.id}</p>
        </div>
        <div className="clip-badges">
          <span className="badge" data-tone={failing ? 'danger' : 'ok'}>
            {clip.verdict}
          </span>
          {clip.intentionalFail ? (
            <span className="badge" data-tone="warn">
              intentional fail
            </span>
          ) : null}
          <span className="badge" data-tone="info">
            {shortDigest(clip.rootDigest)}
          </span>
        </div>
      </header>

      <p className="clip-summary">{clip.summary}</p>

      <ul className="tag-list" aria-label="Motion techniques">
        {clip.technique.map((technique) => (
          <li key={technique} className="tag">
            {technique}
          </li>
        ))}
      </ul>

      <ClipPlayer clip={clip} />

      {failing && clip.reasons.length > 0 ? (
        <p className="clip-reason">
          <strong>Fails:</strong> {clip.reasons.join(' · ')}
        </p>
      ) : null}
    </article>
  )
}
