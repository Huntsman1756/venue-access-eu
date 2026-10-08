"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FlaskConical } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

/**
 * One place that tells every page what it is looking at: synthetic demo data,
 * or an API that cannot be reached (instead of silently empty tables).
 */
export function DatasetBanner() {
  const { data, isError } = useQuery({ queryKey: ["meta"], queryFn: api.meta });

  if (isError) {
    return (
      <div role="alert" className="border-b border-quarantined/30 bg-quarantined/10">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-xs text-quarantined">
          <AlertTriangle size={14} aria-hidden />
          The data API is not reachable right now. Pages below will be empty until it is back.
        </div>
      </div>
    );
  }
  if (data?.dataset_mode !== "demo") return null;
  return (
    <div className="border-b border-unknown/30 bg-unknown/10">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-2 gap-y-1 px-4 py-2 text-xs text-unknown">
        <FlaskConical size={14} aria-hidden />
        <strong className="font-semibold">Synthetic demo data.</strong>
        <span className="text-foreground/80">
          Firms, LEIs and member codes are invented; the pipeline, rules and UI are the real ones.
        </span>
        <Link href="/about#why-demo" className="underline underline-offset-2">
          Why?
        </Link>
      </div>
    </div>
  );
}
