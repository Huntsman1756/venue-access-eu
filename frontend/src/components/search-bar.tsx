"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Landmark, Tag } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function SearchBar({ autoFocus = false, large = false }: { autoFocus?: boolean; large?: boolean }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const router = useRouter();
  const boxRef = useRef<HTMLDivElement>(null);

  const { data } = useQuery({
    queryKey: ["search", q],
    queryFn: () => api.search(q),
    enabled: q.trim().length >= 2,
  });

  type Item = { key: string; href: string; group: string; label: string; sub?: string };
  const items: Item[] = [];
  for (const f of data?.firms ?? [])
    items.push({
      key: `f:${f.participant_id}`, href: `/firms/${encodeURIComponent(f.participant_id)}`,
      group: "Firms", label: f.canonical_name, sub: f.lei ?? f.country ?? undefined,
    });
  for (const v of data?.venues ?? [])
    items.push({
      key: `v:${v.mic}`, href: `/venues/${v.mic}`, group: "Venues",
      label: v.market_name, sub: v.mic,
    });
  for (const c of data?.member_codes ?? [])
    items.push({
      key: `c:${c.member_code}:${c.mic}`, href: `/search?q=${encodeURIComponent(c.member_code)}`,
      group: "Member codes", label: c.member_code, sub: c.mic ?? undefined,
    });

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && items[active]) { router.push(items[active].href); setOpen(false); }
    else if (e.key === "Escape") setOpen(false);
  }

  const groups = [...new Set(items.map((i) => i.group))];
  let idx = -1;

  return (
    <div ref={boxRef} className="relative w-full" role="combobox" aria-expanded={open} aria-haspopup="listbox">
      <input
        autoFocus={autoFocus}
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        placeholder="Search firm, LEI, member code or MIC…"
        aria-label="Search firm, LEI, member code or MIC"
        className={cn(
          "w-full rounded-md border border-border bg-card font-mono text-sm shadow-sm outline-none placeholder:text-muted-foreground focus:border-accent",
          large ? "px-4 py-3 text-base" : "px-3 py-2",
        )}
      />
      {open && items.length > 0 && (
        <div className="absolute z-50 mt-1 max-h-96 w-full overflow-auto rounded-md border border-border bg-card shadow-lg" role="listbox">
          {groups.map((g) => (
            <div key={g}>
              <div className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {g === "Firms" && <Building2 size={10} className="mr-1 inline" />}
                {g === "Venues" && <Landmark size={10} className="mr-1 inline" />}
                {g === "Member codes" && <Tag size={10} className="mr-1 inline" />}
                {g}
              </div>
              {items.filter((i) => i.group === g).map((i) => {
                idx += 1;
                const cur = idx;
                return (
                  <button
                    key={i.key}
                    role="option"
                    aria-selected={cur === active}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-1.5 text-left text-sm",
                      cur === active && "bg-accent/10",
                    )}
                    onMouseEnter={() => setActive(cur)}
                    onClick={() => { router.push(i.href); setOpen(false); }}
                  >
                    <span className="truncate">{i.label}</span>
                    {i.sub && <span className="ml-3 shrink-0 font-mono text-[10px] text-muted-foreground">{i.sub}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
