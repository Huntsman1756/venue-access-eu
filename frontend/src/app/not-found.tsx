import Link from "next/link";

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
