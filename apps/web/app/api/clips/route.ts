import { NextResponse } from 'next/server'
import { allClips, libraryStats } from '@/lib/clips'

/** The library as JSON: the same data the gallery renders, for scripts and agents. */

export const runtime = 'nodejs'

export function GET() {
  const clips = allClips()
  return NextResponse.json({
    stats: libraryStats(),
    clips: clips.map((clip) => ({
      id: clip.id,
      title: clip.title,
      summary: clip.summary,
      technique: clip.technique,
      tags: clip.tags,
      fps: clip.fps,
      width: clip.width,
      height: clip.height,
      frameCount: clip.frameCount,
      durationMs: clip.durationMs,
      verdict: clip.verdict,
      failingAudits: clip.failingAudits,
      reasons: clip.reasons,
      intentionalFail: clip.intentionalFail,
      rootDigest: clip.rootDigest,
      specDigest: clip.specDigest,
      video: clip.video,
    })),
  })
}
