"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";

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
  const { data = [] } = useQuery({
    queryKey: ["changes", since],
    queryFn: () => api.changes(since),
  });
  return (
    <div>
      <h1 className="font-mono text-xl font-bold">Observed changes</h1>
      <p className="mt-1 text-xs text-muted-foreground">
        Change events are derived from differences between good snapshots.
        NEWLY_OBSERVED ≠ “joined”; DISAPPEARED ≠ “left”.
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
                No changes recorded — first snapshot establishes the baseline.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
