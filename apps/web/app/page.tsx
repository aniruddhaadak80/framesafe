import Link from 'next/link'
import { ClipRow } from '@/components/clip-row'
import { allClips, libraryStats } from '@/lib/clips'

/**
 * The gallery.
 *
 * Single column, one clip per row, newest concept first: the rail under each video is the
 * reason to scroll, so the layout gives it the full width of the page rather than boxing
 * it into a card. The page is statically generated from the committed manifests.
 */

export const dynamic = 'force-static'

export default function GalleryPage() {
  const clips = allClips()
  const stats = libraryStats()

  if (clips.length === 0) {
    return (
      <section className="state" data-kind="empty">
        <h2>No clips yet</h2>
        <p>
          A clip exists once <code>clips/&lt;id&gt;/manifest.json</code> does. Render one with{' '}
          <code>framesafe render &lt;id&gt;</code>.
        </p>
      </section>
    )
  }

  return (
    <>
      <section className="hero">
        <span className="eyebrow">v0.1.0 · frame-exact motion graphics</span>
        <h1>Every clip, with the evidence attached.</h1>
        <p>
          {stats.clips} clips · {stats.frames.toLocaleString('en-GB')} rendered frames ·{' '}
          {(stats.videoBytes / 1024 / 1024).toFixed(1)} MB of H.264. Each frame carries a SHA-256 in its clip
          manifest, each clip is audited for flash safety, inter-frame continuity and luminance envelope, and
          the whole library re-renders byte-identically.
        </p>
        <p className="hero-stats mono">
          {stats.passing} pass · {stats.failing} fail ({stats.intentionalFails} intentional) · peak
          inter-frame motion {(stats.maxPeakDelta / 1000).toFixed(3)} · max {stats.maxFlashesInWindow}{' '}
          flashes/s
        </p>
      </section>

      <section className="gallery" aria-label="Clip library">
        {clips.map((clip) => (
          <ClipRow key={clip.id} clip={clip} />
        ))}
      </section>

      <section className="closing" aria-labelledby="reproduce-heading">
        <h2 id="reproduce-heading">Prove any of it yourself</h2>
        <p>
          Nothing on this page is asserted. Clone the repository, install, and re-render the library: every
          frame digest in these manifests is reproduced byte for byte.
        </p>
        <pre>
          <code>{'npm install\nframesafe clips\nframesafe verify all'}</code>
        </pre>
        <p className="muted">
          The deterministic engine is the credibility of the product, so it is the part that cannot be a model
          call. <Link href="/surfaces">See how every surface reaches the same registry.</Link>
        </p>
      </section>
    </>
  )
}
