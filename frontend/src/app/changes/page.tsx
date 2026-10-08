"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const KIND_COLORS: Record<string, string> = {
  NEWLY_OBSERVED: "text-observed",
  REAPPEARED: "text-observed",
  POSSIBLY_DISAPPEARED: "text-unknown",
  CONFIRMED_DISAPPEARED: "text-conflict",
  MEMBER_CODE_CHANGED: "text-accent",
  MEMBERSHIP_TYPE_CHANGED: "text-accent",
};

export default function ChangesPage() {
  const [since, setSince] = useState("1970-01-01");
  const [includeBaseline, setIncludeBaseline] = useState(false);
  const [includeIdentity, setIncludeIdentity] = useState(false);
  const { data = [] } = useQuery({
    queryKey: ["changes", since, includeBaseline, includeIdentity],
    queryFn: () => api.changes(since, includeBaseline, includeIdentity),
  });
  return (
    <div>
      <h1 className="font-mono text-xl font-bold">Observed changes</h1>
      <p className="mt-1 text-xs text-muted-foreground">
        Change events are derived from differences between good snapshots.
        NEWLY_OBSERVED ≠ “joined”; DISAPPEARED ≠ “left”. The first snapshot of
        each source establishes a BASELINE_OBSERVED state, not an admission —
        baseline rows are excluded below unless enabled explicitly.
        IDENTITY_RESOLUTION_CHANGED rows reflect our interpretation layer
        (GLEIF mapping), not market events — also opt-in.
      </p>
      <label className="mt-3 inline-flex items-center gap-2 text-xs text-muted-foreground">
        since
        <input
          type="date"
          value={since}
          onChange={(e) => setSince(e.target.value)}
          className="rounded border border-border bg-card px-2 py-1 font-mono text-xs"
        />
      </label>
      <label className="ml-4 mt-3 inline-flex items-center gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={includeBaseline}
          onChange={(e) => setIncludeBaseline(e.target.checked)}
        />
        include baseline
      </label>
      <label className="ml-4 mt-3 inline-flex items-center gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={includeIdentity}
          onChange={(e) => setIncludeIdentity(e.target.checked)}
        />
        include identity changes
      </label>
      <div className="mt-4 overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/20 text-left">
              {["Date", "Firm", "Membership", "Change", "Old", "New"].map((h) => (
                <th key={h} className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((c) => (
              <tr key={c.change_id} className="border-b border-border/60 last:border-0 hover:bg-muted/10">
                <td className="px-3 py-1.5 font-mono text-xs">{formatDate(c.observed_at)}</td>
                <td className="px-3 py-1.5">
                  <Link href={`/firms/${encodeURIComponent(c.participant_id)}`} className="text-accent hover:underline">
                    {c.canonical_name ?? c.participant_id}
                  </Link>
                </td>
                <td className="px-3 py-1.5 font-mono text-xs">{c.membership_key}</td>
                <td className={`px-3 py-1.5 font-mono text-xs ${KIND_COLORS[c.change_type] ?? ""}`}>
                  {c.change_type}
                </td>
                <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">{c.old_value ?? "—"}</td>
                <td className="px-3 py-1.5 font-mono text-xs">{c.new_value ?? "—"}</td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">
                No changes recorded since this date.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
