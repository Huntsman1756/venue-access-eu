import { AlertTriangle, CheckCircle2, HelpCircle, MinusCircle, ShieldAlert, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const STYLES: Record<string, { icon: typeof CheckCircle2; cls: string; label?: string }> = {
  OBSERVED: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10" },
  NOT_OBSERVED: { icon: MinusCircle, cls: "text-not-observed border-not-observed/40 bg-not-observed/10" },
  UNKNOWN: { icon: HelpCircle, cls: "text-unknown border-unknown/40 bg-unknown/10" },
  QUARANTINED: { icon: ShieldAlert, cls: "text-quarantined border-quarantined/40 bg-quarantined/10" },
  REJECTED: { icon: XCircle, cls: "text-quarantined border-quarantined/40 bg-quarantined/10" },
  UNRESOLVED: { icon: HelpCircle, cls: "text-unknown border-unknown/40 bg-unknown/10" },
  CONFLICT: { icon: AlertTriangle, cls: "text-conflict border-conflict/40 bg-conflict/10" },
  FUZZY_CANDIDATE: { icon: HelpCircle, cls: "text-unknown border-unknown/40 bg-unknown/10" },
  VALIDATED: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10" },
  PUBLISHED: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10" },
  PARSED: { icon: MinusCircle, cls: "text-muted-foreground border-border bg-muted/30" },
  FETCHED: { icon: MinusCircle, cls: "text-muted-foreground border-border bg-muted/30" },
  EXACT_SOURCE_LEI: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10", label: "SOURCE LEI" },
  EXACT_LEGAL_NAME: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10", label: "EXACT NAME" },
  EXACT_NAME_COUNTRY: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10", label: "NAME+COUNTRY" },
  NAME_ADDRESS_MATCH: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10", label: "NAME+ADDR" },
  MANUAL: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10" },
  CURRENT: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10" },
  POSSIBLY_DISAPPEARED: { icon: HelpCircle, cls: "text-unknown border-unknown/40 bg-unknown/10" },
  DISAPPEARED: { icon: MinusCircle, cls: "text-not-observed border-not-observed/40 bg-not-observed/10" },
  REAPPEARED: { icon: CheckCircle2, cls: "text-observed border-observed/40 bg-observed/10" },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const s = STYLES[status] ?? {
    icon: MinusCircle,
    cls: "text-muted-foreground border-border bg-muted/30",
  };
  const Icon = s.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-wide",
        s.cls,
        className,
      )}
      role="status"
      aria-label={`status ${status}`}
    >
      <Icon size={11} aria-hidden />
      {s.label ?? status}
    </span>
  );
}
