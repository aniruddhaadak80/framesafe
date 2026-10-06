import type { Metadata, Viewport } from 'next'
import Link from 'next/link'
import { IBM_Plex_Mono, IBM_Plex_Sans } from 'next/font/google'
import { PRODUCT } from '@/lib/product'
import './globals.css'

const plexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-plex-sans',
  display: 'swap',
})

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-plex-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: `${PRODUCT.name} — frame-exact motion graphics`,
  description: PRODUCT.tagline,
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body>
        <div className="shell">
          <header className="site-header">
            <div className="container">
              <Link href="/" className="brand">
                {PRODUCT.name}
              </Link>
              <nav className="site-nav" aria-label="Main">
                <Link href="/">Gallery</Link>
                <Link href="/surfaces">Surfaces</Link>
                <Link href="/health">Health</Link>
              </nav>
            </div>
          </header>

          <main>
            <div className="container">{children}</div>
          </main>

          <footer className="site-footer">
            <div className="container">
              <span>
                {PRODUCT.name} v{PRODUCT.version} — Apache-2.0. Every frame in this gallery is addressed by
                SHA-256 and re-derivable from its spec.
              </span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  )
}
