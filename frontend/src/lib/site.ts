// Public links and labels shared by the layout and the case-study page.

export const SITE = {
  name: "venue-access-eu",
  tagline: "Observed European trading-venue membership, with evidence.",
  repoUrl: "https://github.com/Huntsman1756/venue-access-eu",
  authorUrl: "https://github.com/Huntsman1756",
  authorName: "H1756",
} as const;

export const NAV = [
  { href: "/venues", label: "Venues" },
  { href: "/compare", label: "Compare" },
  { href: "/changes", label: "Changes" },
  { href: "/sources", label: "Sources" },
  { href: "/methodology", label: "Methodology" },
  { href: "/about", label: "How it's built" },
] as const;

export function repoPath(path: string): string {
  return `${SITE.repoUrl}/blob/main/${path}`;
}
