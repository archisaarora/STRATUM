"""SIPRI Military Expenditure Database Excel parser.

The workbook from sipri.org/databases/milex has several sheets (current
US$, constant US$, share of GDP) in wide format: country rows, year
columns, with a few banner rows above the header. Values are in US$
millions; '...' = unavailable, 'xxx' = country didn't exist.
"""
from __future__ import annotations

import io
import logging
import re

import pandas as pd

log = logging.getLogger(__name__)

SHEET_MEASURES = [
    # (sheet-name regex, output measure name, scale to USD)
    (re.compile(r"current.*us|us.*current", re.IGNORECASE), "expenditure_current_usd", 1e6),
    (re.compile(r"constant.*us", re.IGNORECASE), "expenditure_constant_usd", 1e6),
    (re.compile(r"share.*gdp|%.*gdp", re.IGNORECASE), "expenditure_pct_gdp", 1.0),
]
MISSING = {"...", "..", "xxx", "", "nan", "None", "-"}


def parse_workbook(content: bytes) -> pd.DataFrame:
    """Parse all recognized sheets -> long frame:
    (country_name_raw, year, measure, value)."""
    xls = pd.ExcelFile(io.BytesIO(content))
    frames = []
    for sheet in xls.sheet_names:
        for pattern, measure, scale in SHEET_MEASURES:
            if pattern.search(sheet):
                frames.append(_parse_sheet(xls, sheet, measure, scale))
                break
    if not frames:
        raise ValueError(
            f"No recognizable SIPRI milex sheets in workbook: {xls.sheet_names}"
        )
    out = pd.concat(frames, ignore_index=True)
    log.info("sipri_milex: parsed %d (country, year, measure) rows", len(out))
    return out


def _parse_sheet(xls: pd.ExcelFile, sheet: str, measure: str, scale: float) -> pd.DataFrame:
    raw = xls.parse(sheet, header=None)
    header_idx = _find_header_row(raw)
    header = raw.iloc[header_idx]
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = [str(h).strip() for h in header]

    country_col = next(c for c in df.columns if c.lower().startswith("country"))
    year_cols = [c for c in df.columns if re.fullmatch(r"\d{4}(\.0)?", str(c))]
    df = df[[country_col] + year_cols]
    df = df[df[country_col].notna()]

    long = df.melt(id_vars=[country_col], var_name="year", value_name="value")
    long["year"] = long["year"].astype(str).str.replace(".0", "", regex=False).astype(int)
    long["value"] = long["value"].map(_to_float)
    long = long[long["value"].notna()]
    long["value"] = long["value"] * scale
    long = long.rename(columns={country_col: "country_name_raw"})
    long["measure"] = measure
    return long[["country_name_raw", "year", "measure", "value"]]


def _find_header_row(raw: pd.DataFrame) -> int:
    """The header row is the first containing 'Country' plus 4-digit years."""
    for i in range(min(15, len(raw))):
        vals = [str(v).strip() for v in raw.iloc[i].tolist()]
        has_country = any(v.lower().startswith("country") for v in vals)
        has_years = sum(bool(re.fullmatch(r"\d{4}(\.0)?", v)) for v in vals) >= 2
        if has_country and has_years:
            return i
    raise ValueError("Could not locate SIPRI header row (Country + year columns)")


def _to_float(v: object) -> float | None:
    s = str(v).strip()
    if s in MISSING:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None
