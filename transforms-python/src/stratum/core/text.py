"""Text utilities: company-name normalization, money parsing, stable IDs."""
from __future__ import annotations

import hashlib
import re

_CORP_SUFFIXES = re.compile(
    r"\b(incorporated|corporation|company|limited|holdings?|group|"
    r"inc|corp|co|ltd|llc|llp|lp|plc|gmbh|ag|sa|srl|bv|nv|pty|jsc|pjsc|oao|ooo)\b\.?",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")

_MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million|thousand|bn|m|k)?", re.IGNORECASE)
_MULT = {"billion": 1e9, "bn": 1e9, "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}


def normalize_company(name: object) -> str:
    """Normalize a company name for matching (incl. sanctions matching)."""
    if name is None:
        return ""
    s = str(name).lower().replace("&", " and ")
    s = _CORP_SUFFIXES.sub(" ", s)
    s = _NON_ALNUM.sub(" ", s)
    return _WS.sub(" ", s).strip()


def parse_money(text: str) -> float | None:
    """Extract the first dollar amount from free text -> USD float."""
    m = _MONEY.search(text or "")
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    return value * _MULT.get(unit, 1.0)


def stable_id(*parts: object, prefix: str = "") -> str:
    """Deterministic ID from components — keeps re-runs idempotent."""
    digest = hashlib.sha1("||".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"
