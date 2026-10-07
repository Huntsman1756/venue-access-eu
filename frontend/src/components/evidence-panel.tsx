"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";

const SOURCE_URLS: Record<string, string> = {
  "xetra-participants": "https://www.cashmarket.deutsche-boerse.com/cash-en/trading/admission-to-trading/xetra-participants",
  "euronext-members": "https://connect2.euronext.com/en/membership/resources/member-list",
  "bme-equity-members": "https://www.bolsasymercados.es/en/bme-exchange/trading/participants/equities.html",
  "lse-member-directory": "https://www.londonstockexchange.com/member-directory",
};

export function EvidencePanel({ participantId }: { participantId: string }) {
  const { data } = useQuery({
    queryKey: ["evidence", participantId],
    queryFn: () => api.evidence(participantId),
  });

  if (!data?.length)
    return <p className="text-sm text-muted-foreground">No evidence records.</p>;

  return (
    <div className="space-y-4">
      {data.map((e, i) => (
        <section key={i} className="rounded-md border border-border bg-card p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-mono text-sm font-semibold">{e.source_id}</h3>
            {e.status && <StatusBadge status={e.status} />}
            <a
              href={SOURCE_URLS[e.source_id] ?? "#"}
              target="_blank"
              rel="noreferrer"
              className="ml-auto text-xs text-accent underline-offset-2 hover:underline"
            >
              official source ↗
            </a>
          </div>
          <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-1 font-mono text-[11px] sm:grid-cols-2">
            <div><dt className="inline text-muted-foreground">raw name&nbsp;</dt><dd className="inline">{e.raw_name}</dd></div>
            <div><dt className="inline text-muted-foreground">normalized&nbsp;</dt><dd className="inline">{e.normalized_name}</dd></div>
            <div><dt className="inline text-muted-foreground">raw address&nbsp;</dt><dd className="inline">{e.raw_address ?? "—"}</dd></div>
            <div><dt className="inline text-muted-foreground">record id&nbsp;</dt><dd className="inline">{e.source_record_id ?? "—"}</dd></div>
            <div><dt className="inline text-muted-foreground">key&nbsp;</dt><dd className="inline">{e.source_participant_key}</dd></div>
            <div><dt className="inline text-muted-foreground">method&nbsp;</dt><dd className="inline">{e.method ?? "—"}</dd></div>
            <div><dt className="inline text-muted-foreground">confidence&nbsp;</dt><dd className="inline">{e.confidence != null ? e.confidence.toFixed(2) : "—"}</dd></div>
            <div><dt className="inline text-muted-foreground">candidates&nbsp;</dt><dd className="inline">{e.candidate_count ?? "—"}</dd></div>
            <div><dt className="inline text-muted-foreground">resolved&nbsp;</dt><dd className="inline">{formatDate(e.resolved_at)}</dd></div>
          </dl>
          {e.evidence && (
            <p className="mt-2 border-t border-border pt-2 font-mono text-[11px] text-muted-foreground">
              {e.evidence}
            </p>
          )}
        </section>
      ))}
    </div>
  );
}
