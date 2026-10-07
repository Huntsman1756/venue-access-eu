"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import { MembershipTable } from "@/components/membership-table";
import { EvidencePanel } from "@/components/evidence-panel";

const TABS = ["Memberships", "Checked venues", "Identity & evidence"] as const;

export function FirmView({ id }: { id: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Memberships");
  const { data: firm } = useQuery({
    queryKey: ["participant", id],
    queryFn: () => api.participant(id),
  });
  const { data: memb } = useQuery({
    queryKey: ["memberships", id],
    queryFn: () => api.memberships(id),
  });

  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="font-mono text-2xl font-bold tracking-tight">
          {firm?.canonical_name ?? "…"}
        </h1>
        {firm && <StatusBadge status={firm.identity_status} />}
      </div>
      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-muted-foreground">
        <div><dt className="inline">LEI&nbsp;</dt><dd className="inline">{firm?.lei ?? "—"}</dd></div>
        <div><dt className="inline">Country&nbsp;</dt><dd className="inline">{firm?.country ?? "—"}</dd></div>
        <div><dt className="inline">Method&nbsp;</dt><dd className="inline">{firm?.identity_method ?? "—"}</dd></div>
      </dl>

      <div className="mt-5 flex gap-1 border-b border-border" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`rounded-t px-3 py-1.5 text-sm ${
              tab === t
                ? "border border-b-0 border-border bg-card font-medium"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="pt-4">
        {tab === "Memberships" && (
          <MembershipTable rows={memb?.observed ?? []} />
        )}
        {tab === "Checked venues" && <CheckedVenues rows={memb?.checked ?? []} />}
        {tab === "Identity & evidence" && <EvidencePanel participantId={id} />}
      </div>

      <p className="mt-6 max-w-2xl text-[11px] leading-relaxed text-muted-foreground">
        {memb?.note}
      </p>
    </div>
  );
}

function CheckedVenues({ rows }: { rows: { source_id: string; mic: string; market_family: string; status: string }[] }) {
  const dedup = new Map<string, (typeof rows)[number]>();
  for (const r of rows) dedup.set(`${r.mic}|${r.market_family}`, r);
  const list = [...dedup.values()];
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/20 text-left">
            <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">MIC</th>
            <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Family</th>
            <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Status</th>
            <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Source</th>
          </tr>
        </thead>
        <tbody>
          {list.map((r) => (
            <tr key={`${r.mic}|${r.market_family}`} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-1.5 font-mono">{r.mic}</td>
              <td className="px-3 py-1.5">{r.market_family}</td>
              <td className="px-3 py-1.5"><StatusBadge status={r.status} /></td>
              <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">{r.source_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-2 text-[11px] text-muted-foreground">
        NOT_OBSERVED means no matching membership was found in a successfully
        processed source within its documented scope — not proof of absence of access.
      </p>
    </div>
  );
}
