"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { SearchBar } from "@/components/search-bar";
import { StatusBadge } from "@/components/status-badge";

function SearchInner() {
  const sp = useSearchParams();
  const q = sp.get("q") ?? "";
  const { data } = useQuery({
    queryKey: ["search-page", q],
    queryFn: () => api.search(q),
    enabled: q.length >= 2,
  });
  return (
    <div className="max-w-2xl">
      <SearchBar autoFocus />
      {q && (
        <div className="mt-6 space-y-4">
          {(data?.firms ?? []).map((f) => (
            <div key={f.participant_id} className="rounded-md border border-border bg-card p-3">
              <Link href={`/firms/${encodeURIComponent(f.participant_id)}`}
                className="font-medium text-accent hover:underline">
                {f.canonical_name}
              </Link>
              <div className="mt-1 flex items-center gap-3 font-mono text-xs text-muted-foreground">
                <span>{f.lei ?? "—"}</span>
                <span>{f.country ?? ""}</span>
                <StatusBadge status={f.identity_status} />
              </div>
            </div>
          ))}
          {data && data.firms.length === 0 && (
            <p className="text-sm text-muted-foreground">No firms match {q}.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchInner />
    </Suspense>
  );
}
