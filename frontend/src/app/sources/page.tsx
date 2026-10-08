"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";

export default function SourcesPage() {
  const { data = [] } = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  return (
    <div>
      <h1 className="font-mono text-xl font-bold">Source health</h1>
      <p className="mt-1 text-xs text-muted-foreground">
        A source is fresh only as of its latest <em>successfully processed</em>{" "}
        snapshot. Quarantined snapshots are retained for forensics but never
        create absence events.
      </p>
      <div className="mt-4 space-y-3">
        {data.map((s) => (
          <section key={s.source_id} className="rounded-md border border-border bg-card p-4">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-mono text-sm font-semibold">{s.source_id}</h2>
              {s.latest_status && <StatusBadge status={s.latest_status} />}
              <span className="ml-auto text-[11px] text-muted-foreground">{s.operator}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{s.source_name}</p>
            <dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-1 font-mono text-[11px] sm:grid-cols-4">
              <div><dt className="text-muted-foreground">latest attempt</dt><dd>{formatDate(s.latest_attempt_at)}</dd></div>
              <div><dt className="text-muted-foreground">latest good</dt><dd>{formatDate(s.latest_good_at)}</dd></div>
              <div><dt className="text-muted-foreground">declared update</dt><dd>{s.declared_updated_at ?? "—"}</dd></div>
              <div><dt className="text-muted-foreground">records</dt><dd className="num">{s.record_count ?? "—"}</dd></div>
            </dl>
            <div className="mt-2 flex gap-2 text-[11px] text-muted-foreground">
              <span className="rounded border border-border px-1.5 py-0.5">{s.coverage_scope}</span>
            </div>
          </section>
        ))}
      </div>
      <SnapshotsTable />
    </div>
  );
}

function SnapshotsTable() {
  const { data = [] } = useQuery({ queryKey: ["snapshots"], queryFn: () => api.snapshots() });
  if (!data.length) return null;
  return (
    <div className="mt-8">
      <h2 className="mb-2 font-mono text-sm font-semibold">Recent snapshots</h2>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/20 text-left">
              {["Snapshot", "Status", "Records", "Segments", "Retrieved"].map((h) => (
                <th key={h} className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 30).map((s) => (
              <tr key={s.snapshot_id} className="border-b border-border/60 last:border-0">
                <td className="px-3 py-1.5 font-mono text-xs">{s.snapshot_id}</td>
                <td className="px-3 py-1.5"><StatusBadge status={s.snapshot_status} /></td>
                <td className="px-3 py-1.5 num font-mono text-xs">{s.record_count ?? "—"}</td>
                <td className="px-3 py-1.5 num font-mono text-xs">{s.segment_count ?? "—"}</td>
                <td className="px-3 py-1.5 font-mono text-xs">{formatDate(s.retrieved_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
