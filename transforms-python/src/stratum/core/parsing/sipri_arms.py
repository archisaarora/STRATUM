"""SIPRI Arms Transfers parsers — two export formats supported.

1. Trade register CSV (preferred, transfer-level detail): banner lines
   before the header, fuzzy column names, '()' marking sub-1 TIV
   estimates, delivery-year ranges like '2021-2023'.
2. TIV tables XLSX (fallback when the register export misbehaves):
   recipient/supplier rows x year columns of total TIV — coarser (no
   weapon detail) but enough for arms-transfer velocity and spike signals.
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


REGISTER_COLUMNS = [
    "transfer_id", "supplier", "recipient", "weapon_designation",
    "weapon_description", "order_year", "quantity_ordered",
    "quantity_delivered", "delivery_year_last", "status",
    "tiv_per_unit", "total_tiv",
]

TIV_ANNUAL_MARKER = "tiv_annual"


def parse_tiv_table(content: bytes, *, role: str = "recipient") -> pd.DataFrame:
    """Parse a SIPRI TIV table XLSX (entities x years) into register-shaped
    rows, one per (entity, year), marked status='tiv_annual'.

    `role` is "recipient" for the importer table (the normal case) or
    "supplier" for the exporter table. TIV figures are SIPRI TIV millions,
    matching the register's 'SIPRI TIV for total order' units.
    """
    xls = pd.ExcelFile(io.BytesIO(content))
    frames = []
    for sheet in xls.sheet_names:
        raw = xls.parse(sheet, header=None)
        header_idx = _find_tiv_header_row(raw)
        if header_idx is None:
            continue
        header = [str(v).strip() for v in raw.iloc[header_idx]]
        df = raw.iloc[header_idx + 1:].copy()
        df.columns = header
        entity_col = header[0] if header else None
        year_cols = [c for c in df.columns if re.fullmatch(r"\d{4}(\.0)?", str(c))]
        if not entity_col or not year_cols:
            continue
        df = df[[entity_col] + year_cols]
        df = df[df[entity_col].notna()]
        long = df.melt(id_vars=[entity_col], var_name="year", value_name="total_tiv")
        long["year"] = (long["year"].astype(str)
                        .str.replace(".0", "", regex=False).astype(int))
        long["total_tiv"] = long["total_tiv"].map(_tiv_to_float)
        long = long[long["total_tiv"].notna() & (long["total_tiv"] != 0)]
        long = long.rename(columns={entity_col: role})
        frames.append(long)
    if not frames:
        raise ValueError(
            f"No TIV table sheets recognized in workbook: {xls.sheet_names}")
    out = pd.concat(frames, ignore_index=True)
    other = "supplier" if role == "recipient" else "recipient"
    out[other] = None
    out["weapon_designation"] = None
    out["weapon_description"] = None
    out["order_year"] = out["year"]
    out["delivery_year_last"] = out["year"].astype(float)
    out["quantity_ordered"] = None
    out["quantity_delivered"] = None
    out["tiv_per_unit"] = None
    out["status"] = TIV_ANNUAL_MARKER
    out["transfer_id"] = [
        stable_id("tiv", role, r[role], r["year"], prefix="at_")
        for _, r in out.iterrows()
    ]
    out = out.drop(columns=["year"])
    log.info("sipri_arms tiv table: %d (entity, year) rows", len(out))
    return out[[c for c in REGISTER_COLUMNS if c in out.columns]]


def _find_tiv_header_row(raw: pd.DataFrame) -> int | None:
    """Header = first row whose cells include a run of >=3 four-digit years."""
    for i in range(min(20, len(raw))):
        vals = [str(v).strip() for v in raw.iloc[i].tolist()]
        years = sum(bool(re.fullmatch(r"\d{4}(\.0)?", v)) for v in vals)
        if years >= 3:
            return i
    return None


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
