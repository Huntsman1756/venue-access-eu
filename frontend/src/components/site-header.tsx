"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ThemeToggle } from "@/components/theme";
import { NAV, SITE } from "@/lib/site";
import { cn } from "@/lib/utils";

function Logo() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden className="text-accent">
      <rect x="2" y="13" width="4" height="9" rx="1" fill="currentColor" opacity="0.45" />
      <rect x="10" y="7" width="4" height="15" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="18" y="2" width="4" height="20" rx="1" fill="currentColor" />
    </svg>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  // Remember which path the menu was opened on: navigating closes it without
  // an effect, because the stored path no longer matches.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <Link href="/" className="flex items-center gap-2" aria-label={`${SITE.name} home`}>
          <Logo />
          <span className="font-mono text-sm font-bold tracking-tight">{SITE.name}</span>
        </Link>
        <nav className="ml-auto hidden items-center gap-1 text-sm md:flex" aria-label="Main">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              aria-current={isActive(n.href) ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-card hover:text-foreground",
                isActive(n.href) && "bg-card text-foreground",
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2 md:ml-2">
          <a
            href={SITE.repoUrl}
            className="hidden rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground sm:inline-block"
          >
            GitHub
          </a>
          <ThemeToggle />
          <button
            type="button"
            className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-foreground md:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpenOn(open ? null : pathname)}
          >
            {open ? <X size={16} aria-hidden /> : <Menu size={16} aria-hidden />}
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-nav" aria-label="Main" className="border-t border-border px-4 py-2 md:hidden">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              aria-current={isActive(n.href) ? "page" : undefined}
              className="block rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-card hover:text-foreground"
            >
              {n.label}
            </Link>
          ))}
          <a href={SITE.repoUrl} className="block rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-card">
            GitHub
          </a>
        </nav>
      )}
    </header>
  );
}
