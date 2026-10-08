import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { DatasetBanner } from "@/components/dataset-banner";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import { SITE } from "@/lib/site";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: SITE.name, template: `%s · ${SITE.name}` },
  description:
    "Evidence-backed observations of European trading-venue membership: firms, venues, member codes and provenance, built on an auditable open-source pipeline.",
  openGraph: {
    type: "website",
    siteName: SITE.name,
    title: `${SITE.name} — ${SITE.tagline}`,
    description:
      "An auditable pipeline from official venue directories to entity-resolved, time-aware membership evidence.",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafafa" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0e13" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          // applies stored/system theme before paint to avoid a flash
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('theme');var d=t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d)}catch(e){}`,
          }}
        />
      </head>
      <body className="flex min-h-screen flex-col bg-background text-foreground antialiased">
        <Providers>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-2 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2"
          >
            Skip to content
          </a>
          <SiteHeader />
          <DatasetBanner />
          <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
            {children}
          </main>
          <footer className="mt-16 border-t border-border py-8 text-xs text-muted-foreground">
            <div className="mx-auto grid max-w-6xl gap-6 px-4 sm:grid-cols-[2fr_1fr]">
              <p className="max-w-xl leading-relaxed">
                {SITE.name} records public observations from trading-venue
                sources. A missing observation does not prove that a firm lacks
                direct or indirect access to a venue. Not affiliated with the
                venues shown. Data are observations, not advice.
              </p>
              <ul className="space-y-1.5 sm:text-right">
                <li>
                  <Link href="/about" className="hover:text-foreground">How it&apos;s built</Link>
                </li>
                <li>
                  <a href={SITE.repoUrl} className="hover:text-foreground">Source code (MIT)</a>
                </li>
                <li>
                  <a href={SITE.authorUrl} className="hover:text-foreground">
                    Built by {SITE.authorName}
                  </a>
                </li>
              </ul>
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
