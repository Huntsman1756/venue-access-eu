import type { Metadata } from "next";
import Link from "next/link";

// The 404 inherited the generic site title ("venue-access-eu"), which reads as a
// real page in tabs, history and search results. Give it its own title and keep
// it out of the index.
export const metadata: Metadata = {
  title: "Not found",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <p className="font-mono text-sm text-accent">404</p>
      <h1 className="mt-2 text-2xl font-semibold">Nothing observed here</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        This page does not exist. Like a missing membership, that is not proof of anything else.
      </p>
      <Link href="/" className="mt-6 inline-block rounded-md border border-border px-3 py-1.5 text-sm hover:bg-card">
        Back to search
      </Link>
    </div>
  );
}
