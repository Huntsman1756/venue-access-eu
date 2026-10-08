import type { Metadata } from "next";
import Link from "next/link";
import { SITE, repoPath } from "@/lib/site";

export const metadata: Metadata = {
  title: "How it's built",
  description:
    "Case study: an auditable pipeline from official venue directories to entity-resolved, time-aware membership evidence.",
};

const FLOW = [
  { name: "Fetch", detail: "httpx adapters per venue, polite pacing" },
  { name: "Snapshot", detail: "immutable bytes, SHA-256, retrieved_at" },
  { name: "Parse + gate", detail: "contracts, >15% drop → QUARANTINED" },
  { name: "Resolve", detail: "source LEI → GLEIF name match → review" },
  { name: "History", detail: "intervals + change events, replayable" },
  { name: "Serve", detail: "DuckDB + Parquet → FastAPI → Next.js" },
];

const DECISIONS = [
  {
    adr: "002-observational-semantics",
    title: "Model observations, not memberships",
    why: "Venues publish current-state lists, not validity dates. Saying “joined on” from a capture would be invented data, so first_seen_at is an observation date and nothing more.",
  },
  {
    adr: "005-temporal-disappearance",
    title: "Two confirmations before “gone”",
    why: "A member vanishing between captures is more often a broken download than a resignation. One absence is POSSIBLY_DISAPPEARED; a quarantined capture creates no absence at all.",
  },
  {
    adr: "003-entity-resolution",
    title: "Deterministic identity, no fuzzy merges",
    why: "Euronext and BME publish no LEI. Exact name + country corroboration resolves; anything weaker stays a reviewable candidate instead of silently becoming an entity.",
  },
  {
    adr: "008-source-participant-vs-identity",
    title: "Identity changes never rewrite history",
    why: "History is anchored on the source participant, not the resolved entity. Found the hard way: resolver churn once produced 19 fake “new members” in a second cycle.",
  },
  {
    adr: "007-publication-rights-gate",
    title: "A publication-rights gate in code",
    why: "Not committing raw files is not the same as being allowed to redistribute derived data. Each source carries a rights status, and the pipeline reports what may be published.",
  },
  {
    adr: "001-duckdb-parquet",
    title: "DuckDB + Parquet, no database server",
    why: "A few hundred thousand rows do not need Postgres. One file is the whole dataset: reproducible, diffable and cheap to host.",
  },
];

const QUALITY = [
  ["~100", "offline tests: parsers, gates, resolver, temporal engine, API"],
  ["strict", "mypy across the backend; ruff with security rules"],
  ["invariants", "tests that a resolver flip yields zero membership events"],
  ["synthetic", "every test fixture is invented; a test enforces it"],
];

const STACK = [
  ["Pipeline", "Python 3.12 · httpx · selectolax · pydantic · Typer"],
  ["Storage", "DuckDB · Parquet · append-only snapshots"],
  ["API", "FastAPI, read-only, documented semantics headers"],
  ["Web", "Next.js · React Query · TanStack Table · Tailwind"],
  ["Ops", "Docker · Traefik · GitHub Actions (CI + weekly refresh)"],
];

function Section({ id, title, children }: { id?: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function AboutPage() {
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-14">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">Case study</p>
        <h1 className="mt-3 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
          Turning scattered venue directories into evidence you can audit
        </h1>
        <p className="mt-4 text-pretty text-muted-foreground">
          “Is this firm a member of that exchange?” sounds like a lookup. In Europe
          it means reading a dozen directories in different formats, none of which
          share identifiers, keep history, or say what a missing row means. This
          project answers the question and, more importantly, shows its working.
        </p>
      </header>

      <Section title="The problem">
        <ul className="space-y-2 text-sm leading-relaxed text-muted-foreground">
          <li>• Each venue publishes members its own way: CSV, JSON APIs, paginated HTML.</li>
          <li>• Only some list an LEI; the rest use trading names that must be matched to legal entities.</li>
          <li>• Lists are current-state only. History has to be built from repeated captures.</li>
          <li>• A failed download looks exactly like a mass resignation unless something stops it.</li>
        </ul>
      </Section>

      <Section title="Architecture">
        <ol className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {FLOW.map((f, i) => (
            <li key={f.name} className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[11px] text-accent">{i + 1}</span>
                <span className="font-medium">{f.name}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{f.detail}</p>
            </li>
          ))}
        </ol>
        <p className="mt-3 text-sm text-muted-foreground">
          Full write-up in{" "}
          <a className="text-accent hover:underline" href={repoPath("docs/architecture.md")}>
            docs/architecture.md
          </a>{" "}
          and the{" "}
          <a className="text-accent hover:underline" href={repoPath("docs/data-dictionary.md")}>
            data dictionary
          </a>
          .
        </p>
      </Section>

      <Section title="Decisions that matter">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {DECISIONS.map((d) => (
            <a
              key={d.adr}
              href={repoPath(`docs/adr/${d.adr}.md`)}
              className="group rounded-lg border border-border bg-card p-4 transition-colors hover:border-accent/50"
            >
              <span className="font-mono text-[10px] text-muted-foreground">ADR {d.adr.slice(0, 3)}</span>
              <h3 className="mt-1 font-medium group-hover:text-accent">{d.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{d.why}</p>
            </a>
          ))}
        </div>
      </Section>

      <Section title="How quality is enforced">
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {QUALITY.map(([k, v]) => (
            <div key={k} className="rounded-lg border border-border p-3">
              <dt className="font-mono text-sm font-semibold text-accent">{k}</dt>
              <dd className="mt-0.5 text-sm text-muted-foreground">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-sm text-muted-foreground">
          The semantic contract users rely on is written down in the{" "}
          <Link className="text-accent hover:underline" href="/methodology">methodology</Link>, and
          source health is public on the <Link className="text-accent hover:underline" href="/sources">sources</Link> page.
        </p>
      </Section>

      <Section id="why-demo" title="Why this site shows synthetic data">
        <p className="text-sm leading-relaxed text-muted-foreground">
          Several venues restrict redistribution of data derived from their websites, and the
          rights review is not finished. Until it is, the real dataset stays internal and this
          public instance runs on a generated one: invented firms, test LEIs and member codes,
          produced by the same pipeline, gates and history engine. Anyone can build the real
          dataset locally with <code className="font-mono text-xs">make refresh</code>, subject to
          each source&apos;s terms. See{" "}
          <a className="text-accent hover:underline" href={repoPath("docs/licenses.md")}>
            docs/licenses.md
          </a>
          .
        </p>
      </Section>

      <Section title="Stack">
        <dl className="divide-y divide-border rounded-lg border border-border">
          {STACK.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[7rem_1fr] gap-3 px-4 py-2.5 text-sm">
              <dt className="font-medium">{k}</dt>
              <dd className="text-muted-foreground">{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <footer className="rounded-lg border border-border bg-card p-5">
        <p className="text-sm">
          Designed and built by{" "}
          <a href={SITE.authorUrl} className="font-medium text-accent hover:underline">
            {SITE.authorName}
          </a>
          . The code is MIT-licensed and open for review.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <a href={SITE.repoUrl} className="rounded-md bg-accent px-3 py-1.5 font-medium text-[var(--accent-foreground)] hover:opacity-90">
            View the source
          </a>
          <Link href="/" className="rounded-md border border-border px-3 py-1.5 hover:bg-background">
            Try the explorer
          </Link>
        </div>
      </footer>
    </article>
  );
}
