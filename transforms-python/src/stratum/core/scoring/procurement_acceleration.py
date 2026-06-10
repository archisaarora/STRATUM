"""Transform 4.2 core — procurement acceleration per (country, domain).

Compares the trailing 12 months of classified contract activity against the
12 months before that:

  domain_acceleration_flag = count_12m > 2x prior AND value growth > 50%
  tempo_score              = blend of count ratio and value growth, 0–1
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def procurement_acceleration(
    classified: pd.DataFrame,
    *,
    as_of: pd.Timestamp | None = None,
    count_multiplier: float = 2.0,
    value_growth_pct: float = 50.0,
    min_contracts: int = 3,
) -> pd.DataFrame:
    df = classified.copy()
    df["award_date"] = pd.to_datetime(df["award_date"], errors="coerce")
    df = df[df["award_date"].notna()
            & df["primary_capability_domain"].notna()
            & (df["primary_capability_domain"] != "none")]
    if df.empty:
        return pd.DataFrame(columns=[
            "country_code", "domain", "window_end", "contract_count_12m",
            "contract_value_12m", "prior_count_12m", "prior_value_12m",
            "count_growth_pct", "value_growth_pct", "domain_acceleration_flag",
            "tempo_score",
        ])

    as_of = as_of or df["award_date"].max()
    cur_start = as_of - pd.DateOffset(months=12)
    prior_start = as_of - pd.DateOffset(months=24)

    def window_agg(frame: pd.DataFrame, label: str) -> pd.DataFrame:
        return (
            frame.groupby(["recipient_country", "primary_capability_domain"])
            .agg(**{
                f"{label}_count": ("contract_id", "count"),
                f"{label}_value": ("total_value_usd", "sum"),
            })
            .reset_index()
        )

    cur = window_agg(df[(df["award_date"] > cur_start) & (df["award_date"] <= as_of)], "cur")
    prior = window_agg(
        df[(df["award_date"] > prior_start) & (df["award_date"] <= cur_start)], "prior"
    )
    out = cur.merge(prior, on=["recipient_country", "primary_capability_domain"], how="outer")
    for col in ("cur_count", "prior_count", "cur_value", "prior_value"):
        out[col] = out[col].fillna(0)

    out["count_growth_pct"] = np.where(
        out["prior_count"] > 0,
        (out["cur_count"] - out["prior_count"]) / out["prior_count"] * 100.0,
        np.where(out["cur_count"] >= min_contracts, 999.0, np.nan),
    )
    out["value_growth_pct"] = np.where(
        out["prior_value"] > 0,
        (out["cur_value"] - out["prior_value"]) / out["prior_value"] * 100.0,
        np.where(out["cur_value"] > 0, 999.0, np.nan),
    )
    out["domain_acceleration_flag"] = (
        (out["cur_count"] >= min_contracts)
        & (out["cur_count"] > count_multiplier * out["prior_count"])
        & (out["value_growth_pct"] > value_growth_pct)
    )

    count_ratio = np.where(
        out["prior_count"] > 0, out["cur_count"] / out["prior_count"],
        np.where(out["cur_count"] >= min_contracts, count_multiplier * 2, 0),
    )
    # count ratio of 2x -> 0.5, 4x -> 1.0; value growth 50% -> 0.25, 200% -> 1.0
    tempo = 0.6 * np.clip(count_ratio / 4.0, 0, 1) + 0.4 * np.clip(
        np.nan_to_num(out["value_growth_pct"], nan=0.0) / 200.0, 0, 1
    )
    out["tempo_score"] = np.round(tempo, 4)

    out = out.rename(columns={
        "recipient_country": "country_code",
        "primary_capability_domain": "domain",
        "cur_count": "contract_count_12m",
        "cur_value": "contract_value_12m",
        "prior_count": "prior_count_12m",
        "prior_value": "prior_value_12m",
    })
    out["window_end"] = as_of
    return out
