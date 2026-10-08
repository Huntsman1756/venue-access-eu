"""Explicit, reviewable mapping: source market token -> (MIC, family, label).

Every entry is evidence-backed by ISO 10383 (docs/sources.md). Tokens that are
already valid MICs map to themselves; family labels are source semantics, not
MIC semantics.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketMapping:
    token: str
    mic: str
    family: str  # Cash | Derivatives | Equity | MTF | Latibex
    label: str
    evidence: str = ""


# Euronext CSV column headers. Euronext operates a single MIC per market for
# both cash and derivatives order books on Optiq; the source distinguishes
# cash member codes (X*) from derivatives member codes (D*).
_EURONEXT_CASH = {
    "XAMS": ("XAMS", "Cash", "Euronext Amsterdam"),
    "XBRU": ("XBRU", "Cash", "Euronext Brussels"),
    "XDUB": ("XDUB", "Cash", "Euronext Dublin"),
    "XLIS": ("XLIS", "Cash", "Euronext Lisbon"),
    "XMIL": ("XMIL", "Cash", "Euronext Milan (Borsa Italiana)"),
    "XOSL": ("XOSL", "Cash", "Euronext Oslo"),
    "XPAR": ("XPAR", "Cash", "Euronext Paris"),
}
_EURONEXT_DERIV = {
    "DAMS": ("XAMS", "Derivatives", "Euronext Amsterdam Derivatives"),
    "DBRU": ("XBRU", "Derivatives", "Euronext Brussels Derivatives"),
    "DDUB": ("XDUB", "Derivatives", "Euronext Dublin Derivatives"),
    "DLIS": ("XLIS", "Derivatives", "Euronext Lisbon Derivatives"),
    "DMIL": ("XMIL", "Derivatives", "Euronext Milan Derivatives"),
    "DOSL": ("XOSL", "Derivatives", "Euronext Oslo Derivatives"),
    "DPAR": ("XPAR", "Derivatives", "Euronext Paris Derivatives"),
}

_BME = {
    "madrid-stock-exchange": ("XMAD", "Equity", "Bolsa de Madrid"),
    "barcelona-stock-exchange": ("XBAR", "Equity", "Bolsa de Barcelona"),
    "bilbao-stock-exchange": ("XBIL", "Equity", "Bolsa de Bilbao"),
    "valencia-stock-exchange": ("XVAL", "Equity", "Bolsa de Valencia"),
    "bme-mtf-equity": ("MABX", "MTF", "BME MTF Equity"),
    "latibex": ("XLAT", "Latibex", "Latibex"),
    "bme-growth": ("GROW", "MTF", "BME Growth"),
}

_XETRA = {"XETR": ("XETR", "Cash", "Xetra")}

_LSE_SERVICES = {
    # LSE firm codes carry servicename; today we only see "cash".
    "cash": ("XLON", "Cash", "London Stock Exchange"),
}


def euronext_columns() -> dict[str, MarketMapping]:
    out = {}
    for tok, (mic, fam, label) in {**_EURONEXT_CASH, **_EURONEXT_DERIV}.items():
        out[tok] = MarketMapping(tok, mic, fam, label, "euronext member list CSV column")
    return out


def bme_market(token: str) -> MarketMapping | None:
    t = token.lower().strip()
    t = t.removeprefix("website:bme/markets/")
    hit = _BME.get(t)
    if hit:
        mic, fam, label = hit
        return MarketMapping(token, mic, fam, label, "BME markets[] tag")
    return None


def xetra_market() -> MarketMapping:
    return MarketMapping("XETR", "XETR", "Cash", "Xetra", "ISO 10383 operating MIC")


def lse_market(servicename: str) -> MarketMapping | None:
    hit = _LSE_SERVICES.get(servicename.lower().strip())
    if hit:
        mic, fam, label = hit
        return MarketMapping(servicename, mic, fam, label, "LSE codes[] servicename")
    return None
