"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { Membership } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";

export function MembershipTable({ rows }: { rows: Membership[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!rows.length)
    return <p className="text-sm text-muted-foreground">No observed memberships.</p>;
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/20 text-left">
            <th className="w-6 px-2 py-2" aria-hidden />
            {["Venue", "Family", "Member code", "Type", "Capacity", "Status", "Evidence"].map((h) => (
              <th key={h} className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((m, i) => (
            <MembershipRow key={i} m={m} open={open === i} onToggle={() => setOpen(open === i ? null : i)} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MembershipRow({ m, open, onToggle }: { m: Membership; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className="cursor-pointer border-b border-border/60 hover:bg-muted/10" onClick={onToggle}>
        <td className="px-2 py-1.5 text-muted-foreground">
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </td>
        <td className="px-3 py-1.5 font-mono font-semibold">{m.mic}</td>
        <td className="px-3 py-1.5">{m.market_family}</td>
        <td className="px-3 py-1.5 font-mono text-xs">{m.member_code ?? "—"}</td>
        <td className="px-3 py-1.5 text-xs">{m.membership_type_raw ?? "—"}</td>
        <td className="px-3 py-1.5 font-mono text-xs">{m.capacity_raw ?? "—"}</td>
        <td className="px-3 py-1.5"><StatusBadge status="OBSERVED" /></td>
        <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">{formatDate(m.retrieved_at)}</td>
      </tr>
      {open && (
        <tr className="border-b border-border/60 bg-muted/5">
          <td colSpan={7} className="px-6 py-3">
            <dl className="grid grid-cols-1 gap-x-8 gap-y-1 font-mono text-[11px] sm:grid-cols-2">
              <div><dt className="inline text-muted-foreground">source&nbsp;</dt><dd className="inline">{m.source_id}</dd></div>
              <div><dt className="inline text-muted-foreground">snapshot&nbsp;</dt><dd className="inline">{m.snapshot_id}</dd></div>
              <div><dt className="inline text-muted-foreground">retrieved&nbsp;</dt><dd className="inline">{m.retrieved_at}</dd></div>
              <div><dt className="inline text-muted-foreground">declared&nbsp;</dt><dd className="inline">{m.source_declared_updated_at ?? "—"}</dd></div>
              <div><dt className="inline text-muted-foreground">parser&nbsp;</dt><dd className="inline">{m.parser_version ?? "—"}</dd></div>
              <div className="break-all"><dt className="inline text-muted-foreground">sha256&nbsp;</dt><dd className="inline">{m.raw_sha256}</dd></div>
              <div><dt className="inline text-muted-foreground">segment&nbsp;</dt><dd className="inline">{m.market_family}/{m.mic}</dd></div>
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}
