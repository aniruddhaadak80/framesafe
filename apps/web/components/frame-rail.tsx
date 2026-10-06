'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Clip } from '@/lib/clips'

/**
 * The frame rail: one column per rendered frame, drawn from the manifest's telemetry.
 *
 * This is the product's signature element. Height is the frame's mean relative luminance,
 * the overlaid step line is the inter-frame motion delta, and a red tick marks every frame
 * the flash audit counted as a reversal. Scrubbing the rail seeks the video, so the
 * measurement and the thing being measured are the same gesture.
 *
 * The rail is keyboard-operable (arrows, Home/End) and announces its position, because a
 * scrub bar you can only reach with a mouse is not a control.
 */

interface FrameRailProps {
  readonly clip: Clip
  readonly videoRef: React.RefObject<HTMLVideoElement | null>
  readonly onScrub?: (frame: number) => void
}

const RAIL_HEIGHT = 56

export function FrameRail({ clip, videoRef, onScrub }: FrameRailProps) {
  const railRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)

  const { luma, delta, peak } = useMemo(() => {
    const luminance = clip.telemetry.luma
    const motion = clip.telemetry.delta
    const highest = Math.max(1, ...motion)
    return { luma: luminance, delta: motion, peak: highest }
  }, [clip])

  const seek = useCallback(
    (frame: number) => {
      const bounded = Math.max(0, Math.min(clip.frameCount - 1, frame))
      setActive(bounded)
      const video = videoRef.current
      if (video) {
        video.currentTime = bounded / clip.fps
        if (video.paused) void video.play().catch(() => undefined)
      }
      onScrub?.(bounded)
    },
    [clip.frameCount, clip.fps, onScrub, videoRef],
  )

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const onTimeUpdate = () => setActive(Math.round(video.currentTime * clip.fps))
    video.addEventListener('timeupdate', onTimeUpdate)
    return () => video.removeEventListener('timeupdate', onTimeUpdate)
  }, [clip.fps, videoRef])

  const frameFromPointer = (clientX: number): number => {
    const rail = railRef.current
    if (!rail) return 0
    const bounds = rail.getBoundingClientRect()
    const ratio = (clientX - bounds.left) / bounds.width
    return Math.round(ratio * (clip.frameCount - 1))
  }

  const path = useMemo(() => {
    const width = 100
    const step = clip.frameCount > 1 ? width / (clip.frameCount - 1) : width
    let d = ''
    for (let index = 0; index < clip.frameCount; index += 1) {
      const x = index * step
      const y = RAIL_HEIGHT - ((delta[index] ?? 0) / peak) * (RAIL_HEIGHT - 6) - 3
      d += `${index === 0 ? 'M' : 'L'}${x.toFixed(3)},${y.toFixed(2)}`
    }
    return d
  }, [clip.frameCount, delta, peak])

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const bigStep = Math.max(1, Math.round(clip.frameCount / 10))
    if (event.key === 'ArrowRight') seek(active + 1)
    else if (event.key === 'ArrowLeft') seek(active - 1)
    else if (event.key === 'PageUp') seek(active + bigStep)
    else if (event.key === 'PageDown') seek(active - bigStep)
    else if (event.key === 'Home') seek(0)
    else if (event.key === 'End') seek(clip.frameCount - 1)
    else return
    event.preventDefault()
  }

  const barWidth = 100 / clip.frameCount

  return (
    <div className="rail-wrap">
      <div
        ref={railRef}
        className="rail"
        role="slider"
        tabIndex={0}
        aria-label={`Frame timeline for ${clip.title}`}
        aria-valuemin={0}
        aria-valuemax={clip.frameCount - 1}
        aria-valuenow={active}
        aria-valuetext={`frame ${active} of ${clip.frameCount - 1}`}
        onKeyDown={onKeyDown}
        onPointerDown={(event) => seek(frameFromPointer(event.clientX))}
        onPointerMove={(event) => {
          if (event.buttons === 1) seek(frameFromPointer(event.clientX))
        }}
      >
        <div className="rail-luma" aria-hidden="true">
          {luma.map((value, index) => (
            <span
              key={index}
              className="rail-col"
              style={{ width: `${barWidth}%`, height: `${Math.max(4, (value / 1000) * 100)}%` }}
            />
          ))}
        </div>
        <svg
          className="rail-delta"
          viewBox={`0 0 100 ${RAIL_HEIGHT}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d={path} />
        </svg>
        <div className="rail-flash" aria-hidden="true">
          {clip.telemetry.flashFrames.map((frame) => (
            <span key={frame} className="rail-tick" style={{ left: `${(frame / clip.frameCount) * 100}%` }} />
          ))}
        </div>
        <div
          className="rail-playhead"
          style={{ left: `${(active / clip.frameCount) * 100}%` }}
          aria-hidden="true"
        />
      </div>
      <div className="rail-caption">
        <span className="mono">
          frame {active}/{clip.frameCount - 1}
        </span>
        <span className="rail-legend">
          <span className="rail-key rail-key--luma" aria-hidden="true" /> luminance
          <span className="rail-key rail-key--delta" aria-hidden="true" /> inter-frame motion
          <span className="rail-key rail-key--flash" aria-hidden="true" /> flash reversal
        </span>
      </div>
    </div>
  )
}
