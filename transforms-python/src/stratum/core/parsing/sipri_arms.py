"""SIPRI Arms Transfers 'trade register' CSV parser.

armstransfers.sipri.org exports a CSV with a few banner lines before the
header and column names that drift between releases. We match columns
fuzzily and normalize: TIV values may carry '()' marking sub-1 estimates;
delivery years may be ranges like '2021-2023'.
"""
from __future__ import annotations

import io
import logging
import re

import pandas as pd

from stratum.core.text import stable_id

log = logging.getLogger(__name__)

COLUMN_PATTERNS = {
    "supplier": re.compile(r"^supplier", re.IGNORECASE),
    "recipient": re.compile(r"^recipient", re.IGNORECASE),
    "weapon_designation": re.compile(r"designation", re.IGNORECASE),
    "weapon_description": re.compile(r"description|weapon description", re.IGNORECASE),
    "order_year": re.compile(r"year.*order|order.*year", re.IGNORECASE),
    "quantity_ordered": re.compile(r"number.*order|numbers.*order", re.IGNORECASE),
    "quantity_delivered": re.compile(r"number.*deliver", re.IGNORECASE),
    "delivery_year": re.compile(r"year.*deliver", re.IGNORECASE),
    "status": re.compile(r"^status", re.IGNORECASE),
    "tiv_per_unit": re.compile(r"tiv.*unit", re.IGNORECASE),
    "total_tiv": re.compile(r"tiv.*(total|order|deliver)", re.IGNORECASE),
}


def parse_trade_register(content: bytes | str) -> pd.DataFrame:
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
    lines = text.splitlines()
    header_idx = _find_header_line(lines)
    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])), dtype=str)

    colmap: dict[str, str] = {}
    for target, pattern in COLUMN_PATTERNS.items():
        for col in df.columns:
            if pattern.search(str(col)) and target not in colmap:
                colmap[target] = col
                break
    required = {"supplier", "recipient"}
    if not required.issubset(colmap):
        raise ValueError(f"Unrecognized SIPRI trade-register columns: {list(df.columns)}")

    out = pd.DataFrame({
        target: df[col] if col in df.columns else None
        for target, col in colmap.items()
    })
    out = out[out["supplier"].notna() & out["recipient"].notna()]

    for col in ("tiv_per_unit", "total_tiv"):
        if col in out:
            out[col] = out[col].map(_tiv_to_float)
    for col in ("quantity_ordered", "quantity_delivered"):
        if col in out:
            out[col] = pd.to_numeric(
                out[col].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
            )
    out["order_year"] = pd.to_numeric(out.get("order_year"), errors="coerce")
    out["delivery_year_last"] = out.get("delivery_year", pd.Series(dtype=str)).map(_last_year)

    out["transfer_id"] = [
        stable_id(r.supplier, r.recipient, getattr(r, "weapon_designation", ""),
                  getattr(r, "order_year", ""), i, prefix="at_")
        for i, r in enumerate(out.itertuples(index=False))
    ]
    log.info("sipri_arms: parsed %d transfer rows", len(out))
    return out


def _find_header_line(lines: list[str]) -> int:
    for i, line in enumerate(lines[:30]):
        low = line.lower()
        if "supplier" in low and "recipient" in low:
            return i
    raise ValueError("Could not find SIPRI trade-register header line")


def _tiv_to_float(v: object) -> float | None:
    """'(0.5)' => 0.5 (sub-1 estimate); plain numbers parse directly."""
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    s = s.strip("()")
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _last_year(v: object) -> float | None:
    years = re.findall(r"(19|20)\d{2}", str(v))
    if not years:
        return None
    full = re.findall(r"\b((?:19|20)\d{2})\b", str(v))
    return float(full[-1]) if full else None
