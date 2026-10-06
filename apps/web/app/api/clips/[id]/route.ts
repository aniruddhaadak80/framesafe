import { NextResponse } from 'next/server'
import { clipById } from '@/lib/clips'

/** One clip's full manifest, including its telemetry and per-frame digests. */

export const runtime = 'nodejs'

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const clip = clipById(id)
  if (clip === undefined) {
    return NextResponse.json({ error: 'NOT_FOUND', message: `no clip manifest for "${id}"` }, { status: 404 })
  }
  return NextResponse.json(clip)
}
