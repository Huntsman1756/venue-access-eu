"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/lib/api";
import type { VenueParticipant } from "@/lib/types";
import { DataTable } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";
import { ErrorNote, LoadingNote } from "@/components/data-state";

export function VenueView({ mic }: { mic: string }) {
  const venueQ = useQuery({ queryKey: ["venue", mic], queryFn: () => api.venue(mic) });
  const venue = venueQ.data;
  const participants = venue?.participants ?? [];
  const families = [...new Set(participants.map((p) => p.market_family).filter(Boolean))];

  const columns = useMemo<ColumnDef<VenueParticipant, unknown>[]>(
    () => [
      { accessorKey: "canonical_name", header: "Firm", cell: (c) => (
        <Link href={`/firms/${encodeURIComponent(c.row.original.participant_id)}`}
          className="font-medium text-accent hover:underline">
          {String(c.getValue())}
        </Link>
      ) },
      { accessorKey: "lei", header: "LEI", cell: (c) => <span className="font-mono text-xs">{String(c.getValue() ?? "—")}</span> },
      { accessorKey: "country", header: "CC", cell: (c) => <span className="font-mono">{String(c.getValue() ?? "—")}</span> },
      { accessorKey: "market_family", header: "Family" },
      { accessorKey: "member_code", header: "Member code", cell: (c) => <span className="font-mono text-xs">{String(c.getValue() ?? "—")}</span> },
      { accessorKey: "membership_type_normalized", header: "Type", cell: (c) => <span className="text-xs">{String(c.getValue() ?? "—")}</span> },
      { accessorKey: "identity_status", header: "Identity", cell: (c) => <StatusBadge status={String(c.getValue())} /> },
    ],
    [],
  );

  // A failed request is not an empty venue: say so instead of rendering 0 rows.
  if (venueQ.isPending) return <LoadingNote what={`venue ${mic}`} />;
  if (venueQ.isError) return <ErrorNote what={`venue ${mic}`} error={venueQ.error} />;

  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-4">
        <h1 className="font-mono text-2xl font-bold">{venue?.market_name ?? mic}</h1>
        <span className="font-mono text-sm text-muted-foreground">{mic}</span>
      </div>
      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-muted-foreground">
        <div><dt className="inline">operator&nbsp;</dt><dd className="inline">{venue?.legal_entity_name ?? "—"}</dd></div>
        <div><dt className="inline">op. MIC&nbsp;</dt><dd className="inline">{venue?.operating_mic ?? "—"}</dd></div>
        <div><dt className="inline">category&nbsp;</dt><dd className="inline">{venue?.market_category ?? "—"}</dd></div>
        <div><dt className="inline">country&nbsp;</dt><dd className="inline">{venue?.country ?? "—"}</dd></div>
        <div><dt className="inline">status&nbsp;</dt><dd className="inline">{venue?.mic_status ?? "—"}</dd></div>
      </dl>
      <div className="mt-4 flex gap-4 text-xs text-muted-foreground">
        <span><strong className="text-foreground">{participants.length}</strong> observed participants</span>
        <span><strong className="text-foreground">{new Set(participants.map((p) => p.member_code).filter(Boolean)).size}</strong> member codes</span>
        <span>families: {families.join(", ") || "—"}</span>
      </div>
      <div className="mt-4">
        <DataTable data={participants} columns={columns} filterPlaceholder="Filter firm / code…" />
      </div>
    </div>
  );
}
