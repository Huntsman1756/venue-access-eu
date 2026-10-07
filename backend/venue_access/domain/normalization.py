"""Name and address normalization.

Rules:
- always preserve ``raw_name``; normalization is a *separate* derived field;
- legal-form tokens are *tagged*, not destroyed: ``BANK A SA`` keeps its
  legal-form signature so that ``BANK A SA`` and ``BANK A AG`` never collapse
  into the same key;
- normalization is deterministic and versioned via ``NORMALIZER_VERSION``.
"""

import re
import unicodedata

NORMALIZER_VERSION = "1.0.0"

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[.,;:'\"`´()\[\]{}&/\\\-–—+!?@#$%^*|<>=~_]")  # noqa: RUF001 - intentional real-world punctuation
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9 ]")

# Canonical legal-form forms keyed by spelling variant. Tokens that appear at
# the end of a name (or anywhere) get rewritten to the canonical token so
# "S.A." == "SA", but "SA" != "AG" != "NV".
LEGAL_FORM_VARIANTS: dict[str, str] = {
    "S.A.": "SA",
    "SA": "SA",
    "S.A": "SA",
    "S.A.U.": "SAU",
    "SAU": "SAU",
    "S.L.": "SL",
    "SL": "SL",
    "S.L.U.": "SLU",
    "SLU": "SLU",
    "N.V.": "NV",
    "NV": "NV",
    "B.V.": "BV",
    "BV": "BV",
    "PLC": "PLC",
    "P.L.C.": "PLC",
    "LTD": "LTD",
    "LTD.": "LTD",
    "LIMITED": "LTD",
    "AG": "AG",
    "A.G.": "AG",
    "GMBH": "GMBH",
    "S.P.A.": "SPA",
    "SPA": "SPA",
    "S.R.L.": "SRL",
    "SRL": "SRL",
    "S.A.S.": "SAS",
    "SAS": "SAS",
    "S.À R.L.": "SARL",
    "SARL": "SARL",
    "SE": "SE",
    "S.E.": "SE",
    "OY": "OY",
    "AB": "AB",
    "AS": "AS",
    "A/S": "AS",
    "APS": "APS",
    "GMBH & CO. KG": "GMBHCO",
    "LLP": "LLP",
    "LP": "LP",
    "INC": "INC",
    "LLC": "LLC",
    "S.V.": "SV",
    "SV": "SV",
    "S.G.I.I.C.": "SGIIC",
    "PTY": "PTY",
    "PTE": "PTE",
}

# Multi-word forms must be checked before single tokens.
_MULTI_WORD_FORMS = {k: v for k, v in LEGAL_FORM_VARIANTS.items() if " " in k}

# Legal-form spellings containing punctuation must be rewritten *before* the
# punctuation strip, longest first ("S.A.U." before "S.A." before "S.A").
_PUNCT_FORM_RE = [
    (re.compile(r"(?<![A-Z0-9])" + re.escape(k) + r"(?![A-Z0-9])"), v)
    for k, v in sorted(LEGAL_FORM_VARIANTS.items(), key=lambda kv: -len(kv[0]))
    if any(not c.isalnum() and c != " " for c in k)
]

# Branch markers are recorded but NOT used to collapse entities: a branch is a
# distinct observation handled by entity resolution.
BRANCH_MARKERS = [
    "SUCURSAL",
    "BRANCH",
    "ZWEIGNIEDERLASSUNG",
    "SUCURSALE",
    "FILIALE",
    "SUCCURSALE",
    "LONDON BRANCH",
    "PARIS BRANCH",
    "BRANCH OFFICE",
]


def strip_diacritics(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_name(raw: str | None) -> str:
    """Upper-case, de-accent, collapse punctuation to single spaces.

    Legal-form spellings are canonicalized but retained (``normalize_name``
    output still contains e.g. ``SA`` or ``AG``).
    """
    if not raw:
        return ""
    text = strip_diacritics(raw.strip().upper())
    # Rewrite punctuation-bearing legal-form spellings before punctuation is
    # removed; then space-separated multi-word variants.
    for pattern, canon in _PUNCT_FORM_RE:
        text = pattern.sub(f" {canon} ", text)
    for variant, canon in sorted(_MULTI_WORD_FORMS.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(re.escape(variant) + r"\b", f" {canon} ", text)
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    # Single-token legal forms.
    tokens = text.split(" ")
    out: list[str] = []
    for tok in tokens:
        canon_val = LEGAL_FORM_VARIANTS.get(tok)
        if canon_val is not None:
            out.append(canon_val)
        else:
            out.append(tok)
    return " ".join(out)


def name_stem(normalized: str) -> str:
    """Name minus legal-form tokens — used for candidate generation only.

    Never used alone to assert identity: two different legal forms at the same
    stem may be different entities (e.g. ``FOO SA`` vs ``FOO AG``).
    """
    lf = set(LEGAL_FORM_VARIANTS.values())
    return " ".join(t for t in normalized.split(" ") if t not in lf)


def legal_form_signature(normalized: str) -> str:
    """The sorted legal-form tokens present in a normalized name."""
    lf = set(LEGAL_FORM_VARIANTS.values())
    return "+".join(sorted(t for t in normalized.split(" ") if t in lf))


def has_branch_marker(normalized: str) -> bool:
    return any(m in normalized for m in BRANCH_MARKERS)


def normalize_address(raw: str | None) -> str:
    if not raw:
        return ""
    text = strip_diacritics(raw.strip().upper())
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def normalize_country(raw: str | None) -> str | None:
    """Best-effort country normalization to a stable token (not ISO-3166).

    Returns an ISO-3166 alpha-2 code when confidently derivable, else the
    normalized name. Source adapters may supply ISO codes directly.
    """
    if not raw:
        return None
    t = normalize_address(raw)
    return _COUNTRY_ALIASES.get(t, t)


_COUNTRY_ALIASES = {
    "UNITED KINGDOM": "GB",
    "UK": "GB",
    "GREAT BRITAIN": "GB",
    "ENGLAND": "GB",
    "UNITED STATES": "US",
    "USA": "US",
    "U S A": "US",
    "U S": "US",
    "UNITED STATES OF AMERICA": "US",
    "SPAIN": "ES",
    "FRANCE": "FR",
    "GERMANY": "DE",
    "ITALY": "IT",
    "NETHERLANDS": "NL",
    "THE NETHERLANDS": "NL",
    "HOLLAND": "NL",
    "BELGIUM": "BE",
    "LUXEMBOURG": "LU",
    "IRELAND": "IE",
    "PORTUGAL": "PT",
    "NORWAY": "NO",
    "SWEDEN": "SE",
    "DENMARK": "DK",
    "FINLAND": "FI",
    "SWITZERLAND": "CH",
    "AUSTRIA": "AT",
    "POLAND": "PL",
    "GREECE": "GR",
    "CYPRUS": "CY",
    "MALTA": "MT",
    "ICELAND": "IS",
    "CZECH REPUBLIC": "CZ",
    "CZECHIA": "CZ",
    "SLOVAKIA": "SK",
    "HUNGARY": "HU",
    "ROMANIA": "RO",
    "BULGARIA": "BG",
    "CROATIA": "HR",
    "ESTONIA": "EE",
    "LATVIA": "LV",
    "LITHUANIA": "LT",
    "SLOVENIA": "SI",
    "JERSEY": "JE",
    "GUERNSEY": "GG",
    "ISLE OF MAN": "IM",
    "GIBRALTAR": "GI",
    "LIECHTENSTEIN": "LI",
    "MONACO": "MC",
    "ANDORRA": "AD",
    "CANADA": "CA",
    "AUSTRALIA": "AU",
    "JAPAN": "JP",
    "SINGAPORE": "SG",
    "HONG KONG": "HK",
    "SOUTH KOREA": "KR",
    "KOREA": "KR",
    "UNITED ARAB EMIRATES": "AE",
    "UAE": "AE",
    "ISRAEL": "IL",
    "TURKEY": "TR",
    "SWITZERLAND ": "CH",
    "DENMARK ": "DK",
    "SOUTH AFRICA": "ZA",
    "MEXICO": "MX",
    "BRAZIL": "BR",
    "CHILE": "CL",
    "NORWAY ": "NO",
    "SWEDEN ": "SE",
}
