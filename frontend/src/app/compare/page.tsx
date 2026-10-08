"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { EmptyNote, ErrorNote, LoadingNote } from "@/components/data-state";

const COVERED = ["XETR", "XAMS", "XBRU", "XDUB", "XLIS", "XMIL", "XOSL", "XPAR",
  "XLON", "XMAD", "XBAR", "XBIL", "XVAL", "MABX", "XLAT"];

function CompareInner() {
  const sp = useSearchParams();
  const [a, setA] = useState(sp.get("a") ?? "XETR");
  const [b, setB] = useState(sp.get("b") ?? "XPAR");
  const overlapQ = useQuery({
    queryKey: ["overlap", a, b],
    queryFn: () => api.overlap(a, b),
    enabled: a !== b,
  });
  const data = overlapQ.data;

  return (
    <div>
      <h1 className="font-mono text-xl font-bold">Venue overlap</h1>
      <p className="mt-1 text-xs text-muted-foreground">
        Participants observed on both venues in the latest good snapshots.
        Comparison uses resolved legal entities (LEI), not fuzzy matching.
      </p>
      <div className="mt-4 flex items-center gap-3">
        <Select value={a} onChange={setA} label="Venue A" />
        <span className="text-muted-foreground">vs</span>
        <Select value={b} onChange={setB} label="Venue B" />
      </div>

      {a === b && <p className="mt-4 text-sm text-unknown">Select two different MICs.</p>}
      {a !== b && overlapQ.isPending && <LoadingNote what={`the ${a} / ${b} comparison`} />}
      {a !== b && overlapQ.isError && (
        <ErrorNote what={`the ${a} / ${b} comparison`} error={overlapQ.error} />
      )}
      {a !== b && data && data.counts.both === 0 && (
        <EmptyNote what={`shared participants between ${a} and ${b}`} />
      )}
      {data && a !== b && (
        <>
          <div className="mt-4 flex gap-6 font-mono text-sm">
            <span>{a}: <strong>{data.counts.a}</strong></span>
            <span>{b}: <strong>{data.counts.b}</strong></span>
            <span className="text-observed">both: <strong>{data.counts.both}</strong></span>
          </div>
          <div className="mt-4 overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/20 text-left">
                  {["Firm", "LEI", `${a} code`, `${b} code`, "Identity"].map((h) => (
                    <th key={h} className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.both.map((r) => (
                  <tr key={r.participant_id} className="border-b border-border/60 last:border-0 hover:bg-muted/10">
                    <td className="px-3 py-1.5">
                      <Link href={`/firms/${encodeURIComponent(r.participant_id)}`} className="text-accent hover:underline">
                        {r.canonical_name}
                      </Link>
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.lei ?? "—"}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.member_code_a ?? "—"}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.member_code_b ?? "—"}</td>
                    <td className="px-3 py-1.5"><StatusBadge status={r.identity_status} /></td>
                  </tr>
                ))}
                {data.both.length === 0 && (
                  <tr><td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">No shared observed participants.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Select({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-border bg-card px-2 py-1.5 font-mono text-sm text-foreground"
      >
        {COVERED.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
    </label>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <CompareInner />
    </Suspense>
  );
}
