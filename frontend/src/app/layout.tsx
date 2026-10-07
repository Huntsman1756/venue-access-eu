import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Providers } from "@/components/providers";
import { ThemeToggle } from "@/components/theme";

export const metadata: Metadata = {
  title: { default: "venue-access-eu", template: "%s · venue-access-eu" },
  description:
    "Public evidence of observed European trading-venue membership — firms, venues, member codes, provenance.",
};

const NAV = [
  { href: "/", label: "Home" },
  { href: "/venues", label: "Venues" },
  { href: "/compare", label: "Compare" },
  { href: "/changes", label: "Changes" },
  { href: "/sources", label: "Sources" },
  { href: "/methodology", label: "Methodology" },
];

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
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>
          <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
            <div className="mx-auto flex h-12 max-w-6xl items-center gap-6 px-4">
              <Link href="/" className="flex items-baseline gap-2">
                <span className="font-mono text-sm font-bold tracking-tight">
                  venue-access-eu
                </span>
                <span className="hidden font-mono text-[10px] text-muted-foreground sm:inline">
                  observed membership, with evidence
                </span>
              </Link>
              <nav className="ml-auto flex items-center gap-1 text-sm" aria-label="main">
                {NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="rounded px-2 py-1 text-muted-foreground hover:bg-card hover:text-foreground"
                  >
                    {n.label}
                  </Link>
                ))}
                <ThemeToggle />
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
          <footer className="mt-16 border-t border-border py-6 text-[11px] text-muted-foreground">
            <div className="mx-auto max-w-6xl px-4">
              venue-access-eu records public observations from trading-venue
              sources. A missing observation does not prove that a firm lacks
              direct or indirect access to a venue. Not affiliated with the
              venues shown. Data are observations, not advice.
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
