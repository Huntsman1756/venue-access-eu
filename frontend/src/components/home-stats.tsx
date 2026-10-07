"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

function Stat({ label, value, href }: { label: string; value: string | number; href?: string }) {
  const inner = (
    <div className="flex flex-col items-center rounded-md border border-border bg-card px-6 py-4">
      <span className="num font-mono text-2xl font-semibold">{value}</span>
      <span className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export function HomeStats() {
  const { data } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const stats = data?.stats;
  const latestGood = data?.sources
    ?.map((s) => s.latest_good_at)
    .filter(Boolean)
    .sort()
    .pop();

  return (
    <div className="mt-10 grid w-full max-w-3xl grid-cols-2 gap-3 sm:grid-cols-5">
      <Stat label="Sources" value={data?.sources?.length ?? "…"} href="/sources" />
      <Stat label="Participants" value={stats?.participants ?? "…"} />
      <Stat label="Venues" value={stats?.venues ?? "…"} href="/venues" />
      <Stat label="Observed memb." value={stats?.segment_observations ?? "…"} />
      <Stat label="Last refresh" value={latestGood ? formatDate(latestGood) : "…"} href="/sources" />
    </div>
  );
}
