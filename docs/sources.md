# Source catalog

Investigated 2026-10-07. All endpoints verified live.

## Primary membership sources

### Deutsche Börse / Xetra — Trading Participants

| | |
|---|---|
| Owner | Deutsche Börse AG |
| Page | https://www.cashmarket.deutsche-boerse.com/cash-en/trading/admission-to-trading/xetra-participants |
| Artifact | `.../xetra-participants/4086838!all-csv` (semicolon CSV, UTF-8) |
| Coverage | One row per Member ID; same LEI may appear under multiple Member IDs and offices |
| Columns | `NAME;LEI;MEMBER ID;STREET;NUMBER;ZIP CODE;CITY;COUNTRY;WEBSITE;PHONE` |
| Identity | Source provides LEI → `EXACT_SOURCE_LEI` |
| Declared update | Not present in artifact |
| Completeness | Complete within documented scope (official export of "all trading participants") |
| Absence inference | Allowed |
| Quirks | No venue/market column (all rows are Xetra); phone is partial; LEI present in all observed rows (validated: >80% required by contract test) |
| Observed size | 124 rows (2026-10-07) |

### Euronext — Members List

| | |
|---|---|
| Owner | Euronext N.V. |
| Page | https://connect2.euronext.com/en/membership/resources/member-list (HTML table, paginated) |
| Artifact | `https://connect2.euronext.com/membership/download/csv` (semicolon CSV, quoted, BOM) |
| Coverage | Cash + derivatives member codes for AMS, BRU, DUB, LIS, MIL, OSL, PAR. Athens excluded (separate list at athens.euronext.com, out of v0.1 scope) |
| Layout | Header block (`"Memberlist - Membership Directory"`, `"Updated : DD Mon YYYY"`), then `Member name;Type;XAMS..XPAR;DAMS..DPAR;Address 1;Address 2;Contact` |
| Member codes | In X* (cash) and D* (derivatives) columns per market; may carry a leading TAB; numeric, zero-padded |
| Membership types | `Trading Member (T)`, `Trading-Clearing Member (T)(C)` etc. — preserved raw + normalized |
| Identity | **No LEI** → GLEIF resolution required |
| Declared update | `"Updated : DD Mon YYYY"` inside the file |
| Completeness | Complete within documented scope (official export, matches paginated directory) |
| Absence inference | Allowed |
| Quirks | First request occasionally slow (~10 s server-side generation); rows with no active segment exist and are legitimate; same member may hold several member codes per market |

### BME — Equity Members

| | |
|---|---|
| Owner | BME (SIX Group) |
| Page | https://www.bolsasymercados.es/en/bme-exchange/trading/participants/equities.html |
| Artifact | `https://www.bolsasymercados.es/graphql/execute.json/bme/membersListEquityList_persisted` (AEM GraphQL persisted query, discovered via the `member-list-equity` component JS) |
| Coverage | Equity members of Madrid/Barcelona/Bilbao/Valencia, BME MTF Equity, Latibex |
| Fields | `name, streetAddress, postalCode, city, phone, website, code, isLatinAmerican, markets[], isLiquidityProvider, isLatibexSpecialist` |
| Member code | `code` (e.g. `"8872"`); same code applies across markets[] |
| Identity | **No LEI** → GLEIF resolution required |
| Declared update | Not present |
| Completeness | Complete within documented scope (single persisted query returns the full rendered list) |
| Absence inference | Allowed |
| Quirks | `markets[]` values are `website:bme/markets/*` tags mapped explicitly in `market_map.py`; sibling persisted queries exist for MEFF/clearing (out of v0.1 scope) |
| Observed size | 69 members (2026-10-07) |

### London Stock Exchange — Member Firm Directory

| | |
|---|---|
| Owner | London Stock Exchange plc |
| Page | https://www.londonstockexchange.com/member-directory |
| List endpoint | `https://api.londonstockexchange.com/api/v1/pages?path=member-directory&parameters=page%3D{N}` — 20 firms/page embedded in `components[0].content[0].value.content` |
| Detail endpoint | `https://api.londonstockexchange.com/api/gw/lse/directories/{firmid}` |
| Coverage | Current member firms (status `Active`); 266 firms observed (2026-10-07) |
| Detail fields | `firmid, firmname, status, leicode, registered office + head office, branches[], codes[] (mnemonic, servicename, memberid, firmcode, crestcode, dtccode, euroclearbankcode), instruments, services` |
| Identity | Source provides LEI in firm detail → `EXACT_SOURCE_LEI` |
| Declared update | `lastupdate`/`statusdate` per firm are record metadata, not venue-declared publication dates |
| Completeness | Complete within documented scope (official directory backing the public site) |
| Absence inference | Allowed |
| Quirks | `codes[]` contains duplicate rows differing only in settlement codes — deduplicated on (service, mnemonic, memberid); SPA site, endpoints reverse-engineered and documented; the member-firm information sheets (events) are a separate document stream — roadmap |
| Rate | 0.15 s polite delay between detail fetches |

## Reference sources

### ISO 10383 — Market Identifier Codes

| | |
|---|---|
| Owner | ISO 10383 Registration Authority (SWIFT) |
| Artifact | `https://www.iso20022.org/sites/default/files/ISO10383_MIC/ISO10383_MIC.csv` |
| Coverage | Operating (OPRT) and segment (SGMT) MICs, global |
| Identity | Operator LEI when present |
| Update | Published ~monthly (2nd Monday or next business day); publication date derived from file metadata/dates, not hardcoded |
| Quirks | Dates are `YYYYMMDD` strings; COMMENTS free text |
| Observed size | ~2,880 records (2026-10-07) |

### GLEIF

| | |
|---|---|
| Owner | Global Legal Entity Identifier Foundation |
| API | `https://api.gleif.org/api/v1` — `/lei-records/{lei}`, `/lei-records?filter[entity.names]=`, `/autocompletions`, `/lei-records/{lei}/direct-parent`, `/ultimate-parent` |
| Golden Copy | Documented alternative (`goldencopy.gleif.org`); not used in v0.1 — dataset is O(10³) entities and REST + disk cache is fully reproducible (ADR 003) |
| Identity | Authority for legal-entity identity and Level-2 relationships |
| Terms | CC0 — public domain |

## Licensing / redistribution (initial assessment — not legal advice)

| Source | Raw snapshot in repo | Derived facts | Notes |
|---|---|---|---|
| ISO 10383 | no | yes | Public registry; redistribution of derived venue rows OK with attribution |
| GLEIF | no | yes | CC0 |
| Xetra | no (kept locally) | yes | © Deutsche Börse; derived member-level facts republished with attribution, raw artifacts hashed + kept private |
| Euronext | no | yes | © Euronext; same treatment |
| BME | no | yes | © BME/SIX; same treatment |
| LSE | no | yes | © LSEG; same treatment |

Policy (ADR 004): raw snapshots are **not** redistributed in git/releases;
releases publish derived normalized facts + snapshot metadata (hashes,
timestamps, counts), so every claim remains verifiable while respecting
upstream terms. The `data/raw/` tree is local/object-storage only.
