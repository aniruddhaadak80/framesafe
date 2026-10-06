'use client'

import { useRef } from 'react'
import Link from 'next/link'
import type { Clip } from '@/lib/clips'
import { FrameRail } from './frame-rail'

/**
 * One clip in the gallery: the encoded video and its frame rail, bound together.
 *
 * The video element is the only interactive part; the rail is the measurement layer drawn
 * over the same time axis. Keeping them in one client component means the playhead and the
 * measurement can never drift apart.
 */

interface ClipPlayerProps {
  readonly clip: Clip
}

export function ClipPlayer({ clip }: ClipPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  return (
    <div className="player">
      <video
        ref={videoRef}
        className="player-video"
        src={clip.video?.file ?? undefined}
        width={clip.width}
        height={clip.height}
        aria-label={`${clip.title} — rendered motion graphics clip`}
        controls
        loop
        muted
        playsInline
        preload="metadata"
      >
        Your browser cannot play this clip. The manifest and every frame digest are still verifiable with the
        CLI.
      </video>
      <FrameRail clip={clip} videoRef={videoRef} />
      <div className="player-meta">
        <Link href={`/clips/${clip.id}`} className="player-link">
          Inspect {clip.id} →
        </Link>
        <span className="mono muted">
          {clip.width}×{clip.height} · {clip.fps} fps · {clip.frameCount} frames ·{' '}
          {((clip.durationMs ?? 0) / 1000).toFixed(1)}s
        </span>
      </div>
    </div>
  )
}
