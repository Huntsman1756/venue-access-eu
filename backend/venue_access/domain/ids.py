"""Identifier validation: LEI checksum (ISO 17442) and MIC syntax (ISO 10383)."""

import re

_MIC_RE = re.compile(r"^[A-Z0-9]{4}$")
_LEI_RE = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")

_LEI_MAP = {str(d): d for d in range(10)}
_LEI_MAP.update({chr(ord("A") + i): 10 + i for i in range(26)})


def is_valid_mic(value: str | None) -> bool:
    return bool(value) and bool(_MIC_RE.match(value))


def is_lei_format(value: str | None) -> bool:
    return bool(value) and bool(_LEI_RE.match(value.upper()))


def lei_checksum_ok(lei: str) -> bool:
    """ISO 17442 check-digit validation (MOD 97-10, ISO/IEC 7064)."""
    lei = lei.strip().upper()
    if not is_lei_format(lei):
        return False
    digits = "".join(str(_LEI_MAP[c]) for c in lei)
    # Big-int mod-97 is fine at our scale.
    return int(digits) % 97 == 1


def normalize_lei(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().upper()
    return v if lei_checksum_ok(v) else None


def normalize_mic(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().upper()
    return v if is_valid_mic(v) else None
