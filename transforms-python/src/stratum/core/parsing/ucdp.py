"""UCDP Georeferenced Event Dataset (GED) parser.

UCDP GED is the zero-friction alternative to ACLED: one CSV download from
ucdp.uu.se/downloads (no registration, no key) with georeferenced conflict
events and fatality estimates. We reshape it into the raw_acled_events
schema so the ENTIRE downstream pipeline (clean_acled_events ->
conflict intensity -> profiles) works unchanged.

Coverage notes vs ACLED: GED covers organized violence (state-based,
non-state, one-sided); it skips protests/riots and lags more (annual
release + monthly "candidate events" files, which this parser also
accepts — same columns).
"""
from __future__ import annotations

import io
import logging

import pandas as pd

log = logging.getLogger(__name__)

VIOLENCE_TYPES = {
    1: "State-based conflict",
    2: "Non-state conflict",
    3: "One-sided violence",
}


def parse_ged_to_acled_shape(content: bytes | str | pd.DataFrame) -> pd.DataFrame:
    """GED CSV (or frame) -> rows shaped like the raw_acled_events dataset."""
    if isinstance(content, pd.DataFrame):
        df = content
    else:
        text = (content.decode("utf-8", errors="replace")
                if isinstance(content, bytes) else content)
        df = pd.read_csv(io.StringIO(text), low_memory=False)
    cols = {c.lower(): c for c in df.columns}

    def col(*names: str) -> pd.Series:
        for n in names:
            if n in cols:
                return df[cols[n]]
        return pd.Series([None] * len(df))

    out = pd.DataFrame({
        "event_id_cnty": "GED" + col("id").astype(str),
        "event_date": pd.to_datetime(col("date_start"), errors="coerce")
                        .dt.date.astype(str),
        "year": pd.to_numeric(col("year"), errors="coerce"),
        "event_type": pd.to_numeric(col("type_of_violence"), errors="coerce")
                        .map(VIOLENCE_TYPES),
        "sub_event_type": col("conflict_name", "conflict_new_id"),
        "country": col("country"),
        "admin1": col("adm_1"),
        "location": col("where_description", "where_coordinates"),
        "latitude": pd.to_numeric(col("latitude"), errors="coerce"),
        "longitude": pd.to_numeric(col("longitude"), errors="coerce"),
        "actor1": col("side_a"),
        "actor2": col("side_b"),
        "fatalities": pd.to_numeric(col("best", "best_est"), errors="coerce"),
        "notes": col("source_headline", "source_article"),
        "source": "ucdp_ged",
    })
    out = out[out["country"].notna() & (out["event_date"] != "NaT")]
    log.info("ucdp_ged: %d events converted to ACLED shape", len(out))
    return out
