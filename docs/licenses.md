# Publication rights — source-by-source assessment

Status as of 2026-10-07. This is a good-faith technical assessment, **not
legal advice**. The canonical machine-readable version lives in
`data/curation/publication_rights.yml` and is surfaced by
`quality-report.json`, `venue-access rights`, and `GET /api/v1/rights`.

## Gate semantics

| Status | Meaning | Effect on publish |
|---|---|---|
| `VERIFIED` | Terms confirmed to allow derived redistribution | none |
| `UNCLEAR` | No confirmed restrictive terms, but not verified | dataset marked `CODE_PUBLISHABLE_DATASET_REVIEW` |
| `RESTRICTED` | Public terms restrict systematic retrieval / derived works | dataset marked `CODE_PUBLISHABLE_DATASET_INTERNAL_ONLY` |

The gate never blocks internal processing, local analysis or code
publication. It exists so a public release of `memberships.parquet` / the
hosted UI cannot silently inherit rights the sources do not grant.

## Per-source summary

| Source | Status | Basis |
|---|---|---|
| `gleif` | VERIFIED | GLEIF Golden Copy / API data published under CC0 |
| `iso-10383-mic` | UNCLEAR | MIC list freely published by the RA; broad reuse common but unconfirmed in writing |
| `xetra-participants` | UNCLEAR | Public participant CSV; redistribution terms unconfirmed |
| `euronext-members` | RESTRICTED | ToU restrict systematic retrieval to create databases/compilations and derivative works without prior permission |
| `bme-equity-members` | RESTRICTED | BME states web information is for internal use; commercial use or redistribution requires prior authorization from BME Market Data |
| `lse-member-directory` | RESTRICTED | LSE market-data licensing covers redistribution, derived data and non-display use; whether the public member directory counts as "Exchange Data" needs legal determination |

## Consequences

- Raw snapshots are never published (provenance by SHA-256 + snapshot
  metadata only) — necessary but **not sufficient** for redistribution
  rights of derived data.
- Facts (firm X was listed as member in snapshot Y) are weakly
  copyrightable in most EU jurisdictions, but EU database rights (sui
  generis) can still cover substantial extraction. Volume matters.
- Before a public deployment of the aggregated dataset or the UI
  displaying derived memberships: obtain per-source written
  clarification, or restrict the deployment to sources whose rights are
  VERIFIED (GLEIF), or show derived data only for sources cleared by
  legal review.
- Code, architecture, parsers, schemas, tests, docs and methodology are
  publishable independently of the dataset.

## Review checklist per source

1. Locate the operative terms for the specific endpoint/page (ToU,
   robots.txt, licensing pages, API terms).
2. Classify each field of the matrix in `publication_rights.yml`.
3. Record `evidence_url` + `reviewed_at`.
4. Re-run `venue-access rights` and `publish` to refresh the manifest.
