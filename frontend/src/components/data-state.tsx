"use client";

import type { ReactNode } from "react";

/**
 * Shared loading / failure notices.
 *
 * A failed request must never look like a real zero. Several views used to fall
 * back to `data ?? []`, so an API 500 rendered as "0 observed participants" or
 * "0 both" — indistinguishable from a genuine empty result. Loading, failure and
 * empty are three different things and the UI now says which one it is.
 */

export function LoadingNote({ what }: { what: string }) {
  return (
    <p className="mt-4 text-sm text-muted-foreground" role="status">
      Loading {what}…
    </p>
  );
}

export function ErrorNote({ what, error }: { what: string; error: unknown }) {
  const detail = error instanceof Error ? error.message : String(error);
  return (
    <div
      className="mt-4 rounded-md border border-destructive/50 bg-destructive/5 px-3 py-2 text-sm"
      role="alert"
    >
      <strong className="font-semibold">Could not load {what}.</strong>{" "}
      <span className="text-muted-foreground">
        A request failed — this is not an empty result. Retry in a moment. ({detail})
      </span>
    </div>
  );
}

export function EmptyNote({ what, children }: { what: string; children?: ReactNode }) {
  return (
    <p className="mt-4 text-sm text-muted-foreground">
      No {what} in this dataset.{children ? <> {children}</> : null}
    </p>
  );
}
