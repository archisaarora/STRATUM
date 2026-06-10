"""OpenSanctions targets.simple.csv parser."""
from __future__ import annotations

import io
import logging

import pandas as pd

from stratum.core.text import normalize_company

log = logging.getLogger(__name__)

ORG_SCHEMAS = {"Company", "Organization", "LegalEntity", "PublicBody"}


def parse_targets(content: bytes | str) -> pd.DataFrame:
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    return tidy_targets(pd.read_csv(io.StringIO(text), dtype=str))


def tidy_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a targets frame; idempotent (accepts raw upload columns or
    an already-tidied frame)."""
    if "entity_id" in df.columns:  # already tidy (API-ingested raw dataset)
        out = df.copy()
        out["is_organization"] = out["schema"].isin(ORG_SCHEMAS)
        out["normalized_name"] = out["name"].map(normalize_company)
        return out
    cols = {c.lower(): c for c in df.columns}

    def col(name: str) -> pd.Series:
        c = cols.get(name)
        return df[c] if c else pd.Series([None] * len(df))

    out = pd.DataFrame({
        "entity_id": col("id"),
        "schema": col("schema"),
        "name": col("name"),
        "aliases": col("aliases"),
        "countries": col("countries"),
        "sanction_datasets": col("datasets"),
        "sanctions": col("sanctions"),
        "first_seen": col("first_seen"),
        "last_seen": col("last_seen"),
    })
    out = out[out["entity_id"].notna() & out["name"].notna()]
    out["is_organization"] = out["schema"].isin(ORG_SCHEMAS)
    out["normalized_name"] = out["name"].map(normalize_company)
    log.info("opensanctions: %d entities (%d organizations)",
             len(out), int(out["is_organization"].sum()))
    return out


def build_org_name_index(clean: pd.DataFrame) -> set[str]:
    """Normalized org names + aliases, for matching contract recipients."""
    orgs = clean[clean["is_organization"]]
    names: set[str] = set(orgs["normalized_name"].dropna())
    for aliases in orgs["aliases"].dropna():
        for alias in str(aliases).split(";"):
            n = normalize_company(alias)
            if len(n) >= 5:  # short aliases create false positives
                names.add(n)
    names.discard("")
    return names
