"""Transform 2.5 core — arms-transfer velocity per recipient country."""
from __future__ import annotations

import numpy as np
import pandas as pd


def transfer_velocity(
    transfers: pd.DataFrame,   # clean_sipri_arms_transfers
    *,
    window_years: int = 3,
    spike_multiplier: float = 2.0,
) -> pd.DataFrame:
    """Annual TIV received per country with rolling baseline and spike flag.

    Uses delivery year when present (capability actually arriving),
    falling back to order year.
    """
    df = transfers.copy()
    df["effective_year"] = df["delivery_year_last"].fillna(df["order_year"])
    df = df[df["effective_year"].notna() & df["total_tiv"].notna()]
    df["effective_year"] = df["effective_year"].astype(int)

    annual = (
        df.groupby(["recipient_country", "effective_year"])
        .agg(
            total_tiv=("total_tiv", "sum"),
            transfer_count=("transfer_id", "count"),
            top_category=(
                "weapon_description",
                lambda s: s.value_counts().index[0] if len(s) else None,
            ),
        )
        .reset_index()
        .rename(columns={"effective_year": "year"})
        .sort_values(["recipient_country", "year"])
    )

    grouped = annual.groupby("recipient_country")["total_tiv"]
    annual["rolling_avg_tiv_3y"] = grouped.transform(
        lambda s: s.shift(1).rolling(window_years, min_periods=2).mean()
    )
    prev = grouped.shift(1)
    annual["tiv_yoy_growth_pct"] = np.where(
        prev > 0, (annual["total_tiv"] - prev) / prev * 100.0, np.nan
    )
    annual["transfer_spike_flag"] = (
        (annual["rolling_avg_tiv_3y"] > 0)
        & (annual["total_tiv"] > spike_multiplier * annual["rolling_avg_tiv_3y"])
    )
    annual["spike_magnitude"] = np.where(
        annual["rolling_avg_tiv_3y"] > 0,
        annual["total_tiv"] / annual["rolling_avg_tiv_3y"],
        np.nan,
    )
    return annual
