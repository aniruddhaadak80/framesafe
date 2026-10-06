import type { Metadata } from 'next'
import { SURFACES } from '@/lib/product'

export const metadata: Metadata = { title: 'Surfaces' }

const TONE = { shipped: 'ok', omitted: 'warn' } as const

export default function SurfacesPage() {
  const shipped = SURFACES.filter((surface) => surface.status === 'shipped')
  const omitted = SURFACES.filter((surface) => surface.status === 'omitted')

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Capability</span>
        <h1>Surfaces</h1>
        <p>
          Every capability is a Tool in one registry, reachable identically from each surface below. What is
          missing is listed too, because an omission you can see is a decision; an omission you have to
          discover is a gap.
        </p>
      </section>

      {SURFACES.length === 0 ? (
        <p className="state" data-kind="empty">
          No surfaces registered.
        </p>
      ) : (
        <>
          <h2>Shipped</h2>
          <div className="grid">
            {shipped.map((surface) => (
              <article className="card" key={surface.id}>
                <span className="badge" data-tone={TONE[surface.status]}>
                  {surface.status}
                </span>
                <h3>{surface.title}</h3>
                <p>{surface.summary}</p>
                <code className="muted">{surface.id}</code>
              </article>
            ))}
          </div>

          <h2 style={{ marginTop: 'var(--space-7)' }}>Deliberately omitted</h2>
          <div className="grid">
            {omitted.map((surface) => (
              <article className="card" key={surface.id}>
                <span className="badge" data-tone={TONE[surface.status]}>
                  {surface.status}
                </span>
                <h3>{surface.title}</h3>
                <p>{surface.why ?? surface.summary}</p>
                <code className="muted">{surface.id}</code>
              </article>
            ))}
          </div>
        </>
      )}
    </>
  )
}
