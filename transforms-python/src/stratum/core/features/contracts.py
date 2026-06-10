"""Transform 2.3 core — merge USASpending + DoD contracts; company rollup
with OpenSanctions cross-referencing."""
from __future__ import annotations

import pandas as pd

from stratum.core.text import normalize_company, stable_id

MERGED_COLUMNS = [
    "contract_id", "source", "recipient_name", "recipient_country",
    "awarding_agency", "award_date", "total_value_usd",
    "description_raw_text", "naics_code", "psc_code",
]


def merge_contract_sources(
    usaspending: pd.DataFrame | None, dod: pd.DataFrame | None
) -> pd.DataFrame:
    """Standardize both sources to MERGED_COLUMNS, union, dedupe.

    DoD daily announcements and USASpending overlap; we keep both rows but
    dedupe within-source on contract_id (idempotency on re-runs).
    """
    frames = []
    if usaspending is not None and len(usaspending):
        u = usaspending.copy()
        frames.append(pd.DataFrame({
            "contract_id": u["award_id"].map(lambda x: stable_id(x, prefix="usa_")),
            "source": "usaspending",
            "recipient_name": u["recipient_name"],
            "recipient_country": u.get("recipient_country", "USA"),
            "awarding_agency": u["awarding_agency_name"],
            "award_date": pd.to_datetime(
                u["period_of_performance_start_date"], errors="coerce"),
            "total_value_usd": pd.to_numeric(
                u["total_obligated_amount"], errors="coerce"),
            "description_raw_text": u["award_description"],
            "naics_code": u.get("naics_code"),
            "psc_code": u.get("product_or_service_code"),
        }))
    if dod is not None and len(dod):
        d = dod.copy()
        frames.append(pd.DataFrame({
            "contract_id": d["contract_id"],
            "source": "dod",
            "recipient_name": d["contractor_name"],
            "recipient_country": d.get("recipient_country", "USA"),
            "awarding_agency": d.get("contracting_command", "Department of Defense"),
            "award_date": pd.to_datetime(d["contract_date"], errors="coerce"),
            "total_value_usd": pd.to_numeric(d["contract_value_usd"], errors="coerce"),
            "description_raw_text": d["description_text"],
            "naics_code": None,
            "psc_code": None,
        }))
    if not frames:
        return pd.DataFrame(columns=MERGED_COLUMNS)

    merged = pd.concat(frames, ignore_index=True)[MERGED_COLUMNS]
    merged = merged[
        merged["description_raw_text"].notna()
        & (merged["description_raw_text"].astype(str).str.len() > 20)
    ]
    merged = merged.drop_duplicates(subset=["contract_id"], keep="first")
    merged["recipient_country"] = merged["recipient_country"].fillna("USA")
    return merged.reset_index(drop=True)


def company_rollup(
    classified_contracts: pd.DataFrame,
    sanctioned_org_names: set[str],
) -> pd.DataFrame:
    """One row per company with contract aggregates + sanctions match."""
    df = classified_contracts.copy()
    df["normalized_name"] = df["recipient_name"].map(normalize_company)
    df = df[df["normalized_name"] != ""]

    def first_domain(s: pd.Series) -> str | None:
        s = s.dropna()
        s = s[s != "none"]
        return s.value_counts().index[0] if len(s) else None

    out = (
        df.groupby("normalized_name")
        .agg(
            company_name=("recipient_name", "first"),
            country_of_incorporation=("recipient_country", "first"),
            total_contract_value_usd=("total_value_usd", "sum"),
            contract_count=("contract_id", "count"),
            primary_capability_domain=("primary_capability_domain", first_domain),
            first_award=("award_date", "min"),
            last_award=("award_date", "max"),
            avg_threat_relevance=("threat_relevance_score", "mean"),
        )
        .reset_index()
    )
    out["company_id"] = out["normalized_name"].map(lambda n: stable_id(n, prefix="co_"))
    out["opensanctions_match"] = out["normalized_name"].isin(sanctioned_org_names)
    out["is_sanctioned"] = out["opensanctions_match"]
    return out
