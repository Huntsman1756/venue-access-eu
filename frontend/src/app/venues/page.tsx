"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/lib/api";
import type { Venue } from "@/lib/types";
import { DataTable } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";

export default function VenuesPage() {
  const { data = [] } = useQuery({ queryKey: ["venues"], queryFn: api.venues });
  const columns = useMemo<ColumnDef<Venue, unknown>[]>(
    () => [
      { accessorKey: "mic", header: "MIC", cell: (c) => (
        <Link href={`/venues/${c.getValue()}`} className="font-mono font-semibold text-accent hover:underline">
          {String(c.getValue())}
        </Link>
      ) },
      { accessorKey: "operating_mic", header: "Op. MIC", cell: (c) => <span className="font-mono">{String(c.getValue())}</span> },
      { accessorKey: "market_name", header: "Market" },
      { accessorKey: "mic_type", header: "Type", cell: (c) => <span className="font-mono text-xs">{String(c.getValue())}</span> },
      { accessorKey: "market_category", header: "Cat.", cell: (c) => <span className="font-mono text-xs">{String(c.getValue() ?? "—")}</span> },
      { accessorKey: "country", header: "CC", cell: (c) => <span className="font-mono">{String(c.getValue() ?? "—")}</span> },
      { accessorKey: "mic_status", header: "Status", cell: (c) => (
        <StatusBadge status={c.getValue() === "ACTIVE" ? "OBSERVED" : "NOT_OBSERVED"} />
      ) },
    ],
    [],
  );
  return (
    <div>
      <h1 className="font-mono text-xl font-bold">Venues — ISO 10383 registry</h1>
      <p className="mb-4 mt-1 text-xs text-muted-foreground">
        {data.length} market identifier codes. Only venues covered by membership
        sources carry observations.
      </p>
      <DataTable data={data} columns={columns} filterPlaceholder="Filter MIC / market…" />
    </div>
  );
}
