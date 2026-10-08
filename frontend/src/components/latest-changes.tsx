"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const LABEL: Record<string, string> = {
  NEWLY_OBSERVED: "newly observed",
  REAPPEARED: "reappeared",
  POSSIBLY_DISAPPEARED: "possibly gone",
  CONFIRMED_DISAPPEARED: "confirmed gone",
  MEMBER_CODE_CHANGED: "code changed",
  MEMBERSHIP_TYPE_CHANGED: "type changed",
};

const TONE: Record<string, string> = {
  NEWLY_OBSERVED: "text-observed",
  REAPPEARED: "text-observed",
  POSSIBLY_DISAPPEARED: "text-unknown",
  CONFIRMED_DISAPPEARED: "text-conflict",
};

export function LatestChanges() {
  const { data: raw, isPending } = useQuery({
    queryKey: ["changes", "latest"],
    queryFn: () => api.changes(undefined, false, false, 60),
  });
  // one row per firm so a single busy firm does not fill the panel
  const seen = new Set<string>();
  const data = raw
    ?.filter((c) => {
      const k = c.participant_id ?? c.change_id;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    })
    .slice(0, 8);

  return (
    <div className="min-w-0 rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Latest observed changes</h2>
        <Link href="/changes" className="inline-flex items-center gap-1 text-xs text-accent hover:underline">
          All changes <ArrowRight size={12} aria-hidden />
        </Link>
      </div>
      <ul className="min-w-0 divide-y divide-border/70">
        {isPending &&
          Array.from({ length: 5 }, (_, i) => (
            <li key={i} className="px-4 py-3">
              <div className="h-4 w-2/3 animate-pulse rounded bg-border/60" />
            </li>
          ))}
        {data?.map((c) => {
          const [, mic, family] = c.membership_key.split("|");
          return (
            <li key={c.change_id} className="flex min-w-0 items-baseline gap-3 px-4 py-2.5 text-sm">
              <span className="w-20 shrink-0 font-mono text-[11px] text-muted-foreground">
                {formatDate(c.observed_at)}
              </span>
              <span className="w-0 min-w-0 flex-1 truncate">
                {c.participant_id ? (
                  <Link href={`/firms/${encodeURIComponent(c.participant_id)}`} className="hover:underline">
                    {c.canonical_name ?? c.participant_id}
                  </Link>
                ) : (
                  (c.canonical_name ?? "—")
                )}
                <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                  {mic} {family}
                </span>
              </span>
              <span className={`shrink-0 font-mono text-[11px] ${TONE[c.change_type] ?? "text-accent"}`}>
                {LABEL[c.change_type] ?? c.change_type}
              </span>
            </li>
          );
        })}
        {data?.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-muted-foreground">
            No changes yet — only the first (baseline) snapshot has been captured.
          </li>
        )}
      </ul>
    </div>
  );
}
