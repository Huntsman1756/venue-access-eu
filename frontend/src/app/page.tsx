import type { Metadata } from "next";
import { ArrowRight, Fingerprint, History, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { HomeStats } from "@/components/home-stats";
import { LatestChanges } from "@/components/latest-changes";
import { SearchBar } from "@/components/search-bar";

export const metadata: Metadata = {
  title: "European venue membership, with evidence",
};

const EXAMPLES = [
  { href: "/venues/XETR", label: "Members of XETR" },
  { href: "/compare?a=XETR&b=XPAR", label: "XETR vs XPAR overlap" },
  { href: "/search?q=securities", label: "Search “securities”" },
  { href: "/changes", label: "What changed recently" },
];

const PIPELINE = [
  { step: "Capture", text: "Official venue directories are fetched and stored as immutable, hashed snapshots." },
  { step: "Gate", text: "Schema checks and a >15% drop rule quarantine broken captures before they count." },
  { step: "Resolve", text: "Members are matched to legal entities (LEI) by deterministic, auditable rules." },
  { step: "Track", text: "Snapshots become intervals and change events; absence needs two confirmations." },
];

const PRINCIPLES = [
  {
    icon: Fingerprint,
    title: "Every claim has provenance",
    text: "Each membership links to the snapshot, its SHA-256, retrieval time, parser version and identity method.",
  },
  {
    icon: ShieldCheck,
    title: "Absence is never assumed",
    text: "NOT_OBSERVED is scoped to a source that was processed successfully. Failed or partial sources answer UNKNOWN.",
  },
  {
    icon: History,
    title: "History you can replay",
    text: "Intervals and events are rebuilt deterministically from observations; identity changes never rewrite membership history.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-20">
      <section className="relative pt-6 text-center sm:pt-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-8 -z-10 mx-auto h-64 max-w-3xl rounded-full bg-accent/10 blur-3xl"
        />
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">
          Open data pipeline · EU market structure
        </p>
        <h1 className="mx-auto mt-4 max-w-3xl text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
          Who is a member of which European venue — <span className="text-accent">and how do we know?</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-pretty text-base text-muted-foreground">
          Search firms, LEIs, member codes and venues across Xetra, Euronext, BME and the
          London Stock Exchange. Every answer traces back to a captured public source.
        </p>
        <div className="mx-auto mt-8 max-w-2xl">
          <SearchBar large autoFocus />
        </div>
        <ul className="mx-auto mt-4 flex max-w-2xl flex-wrap justify-center gap-2" aria-label="Examples">
          {EXAMPLES.map((e) => (
            <li key={e.href}>
              <Link
                href={e.href}
                className="inline-block rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-accent/60 hover:text-foreground"
              >
                {e.label}
              </Link>
            </li>
          ))}
        </ul>
        <div className="mt-10 flex justify-center">
          <HomeStats />
        </div>
      </section>

      <section aria-labelledby="pipeline-title">
        <h2 id="pipeline-title" className="text-xl font-semibold tracking-tight">How an observation is made</h2>
        <ol className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {PIPELINE.map((p, i) => (
            <li key={p.step} className="relative rounded-lg border border-border bg-card p-4">
              <span className="font-mono text-xs text-accent">0{i + 1}</span>
              <h3 className="mt-1 font-semibold">{p.step}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{p.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="principles-title" className="grid min-w-0 grid-cols-1 gap-8 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2 id="principles-title" className="text-xl font-semibold tracking-tight">Built to be trusted, not just browsed</h2>
          <ul className="mt-6 space-y-5">
            {PRINCIPLES.map((p) => (
              <li key={p.title} className="flex gap-3">
                <p.icon size={18} className="mt-0.5 shrink-0 text-accent" aria-hidden />
                <div>
                  <h3 className="font-medium">{p.title}</h3>
                  <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">{p.text}</p>
                </div>
              </li>
            ))}
          </ul>
          <Link
            href="/about"
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
          >
            Read how it&apos;s built <ArrowRight size={14} aria-hidden />
          </Link>
        </div>
        <LatestChanges />
      </section>
    </div>
  );
}
