"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { ErrorNote, LoadingNote } from "@/components/data-state";

function shortDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

function Stat({ label, value, href }: { label: string; value: string | number; href?: string }) {
  const inner = (
    <div className="flex h-full flex-col items-center justify-center rounded-lg border border-border bg-card px-4 py-3 transition-colors hover:border-accent/50">
      <span className="num font-mono text-xl font-semibold sm:text-2xl">{value}</span>
      <span className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export function HomeStats() {
  const metaQ = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const data = metaQ.data;
  const stats = data?.stats;
  const latestGood = data?.sources
    ?.map((s) => s.latest_good_at)
    .filter(Boolean)
    .sort()
    .pop();
  const fmt = (n: number | undefined) => (n === undefined ? "…" : n.toLocaleString("en"));

  // The summary is either loading, failed or real: never render zeros in place
  // of a request that did not answer.
  if (metaQ.isPending) return <LoadingNote what="the dataset summary" />;
  if (metaQ.isError) return <ErrorNote what="the dataset summary" error={metaQ.error} />;

  return (
    <div className="grid w-full max-w-3xl grid-cols-2 gap-3 sm:grid-cols-5">
      <Stat label="Sources" value={data?.sources?.length ?? "…"} href="/sources" />
      <Stat label="Firms" value={fmt(stats?.participants)} />
      <Stat label="Venues" value={fmt(stats?.venues)} href="/venues" />
      <Stat label="Current memberships" value={fmt(stats?.current_memberships)} />
      <Stat label="Last capture" value={latestGood ? shortDate(latestGood) : "…"} href="/sources" />
    </div>
  );
}
