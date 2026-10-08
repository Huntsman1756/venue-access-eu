import type { Metadata } from "next";

export const metadata: Metadata = { title: "Methodology" };

const SECTIONS = [
  {
    title: "What we observe",
    body: `venue-access-eu records public observations of trading-venue
membership captured from official venue sources. An observation means: "this
firm appeared as a member in a specific captured artifact at a specific
time." Nothing more is claimed.`,
  },
  {
    title: "What we do not observe",
    body: `The dataset does not attempt to identify private routing
arrangements, DMA/DEA relationships, sponsored-access arrangements unless
explicitly published by the venue, contractual broker relationships, or a
firm's actual ability to execute a given order. Membership, access, routing,
clearing and settlement are distinct concepts; only observed membership is
modelled.`,
  },
  {
    title: "Absence semantics",
    body: `NOT_OBSERVED means: no matching membership was found in a
successfully processed source whose documented scope covers the question. It
is never rendered as "has no access". When a source is partial, failed, or
quarantined, the answer is UNKNOWN — with the reason attached.`,
  },
  {
    title: "Temporal semantics",
    body: `first_seen_at means "present in a good snapshot taken that day" —
not "became a member that day". Sources do not publish valid_from/valid_to
for memberships, so we never fabricate them. A disappearance requires two
consecutive good snapshots to be CONFIRMED; a single absence is only
POSSIBLY_DISAPPEARED. Quarantined snapshots create no absence events.`,
  },
  {
    title: "Identity resolution",
    body: `Participants are matched to GLEIF legal entities (LEI) by a
deterministic, auditable pipeline: source-provided LEI when the venue
publishes it, else exact normalized legal-name match corroborated by
country/address evidence. Fuzzy matches produce review candidates, never
automatic merges. Ambiguous names stay UNRESOLVED. Manual overrides are
recorded with reviewer, reason and date.`,
  },
  {
    title: "Provenance",
    body: `Every public claim traces to: raw artifact bytes (SHA-256),
retrieval timestamp, official URL, parser version, normalized record hash,
and the identity-resolution method. Snapshots are immutable.`,
  },
  {
    title: "Source quality gates",
    body: `A snapshot that drops >15% of records or segments versus the
previous good snapshot, returns zero rows, fails schema checks, or looks
like a block/error page is QUARANTINED. Mass "disappearances" are treated as
pipeline failures until proven otherwise.`,
  },
  {
    title: "Known limitations",
    body: `Coverage v0.1: Xetra, Euronext (7 markets, cash+derivatives), BME
equity members, LSE member firm directory. Not covered: Cboe, Aquis,
Athens, Nasdaq Nordic/Baltic, SIX, Warsaw, Eurex, CCP membership.
GLEIF Level-2 relationships are populated only for resolved LEIs.
Snapshots are periodic observations, not a continuous feed.`,
  },
];

export default function MethodologyPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="font-mono text-xl font-bold">Methodology</h1>
      <p className="mt-1 text-xs text-muted-foreground">
        The semantic contract of this dataset.
      </p>
      <div className="mt-6 space-y-6">
        {SECTIONS.map((s) => (
          <section key={s.title}>
            <h2 className="text-sm font-semibold">{s.title}</h2>
            <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
              {s.body}
            </p>
          </section>
        ))}
      </div>
    </div>
  );
}
