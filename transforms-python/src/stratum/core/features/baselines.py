"""Transform 2.1/2.2 core — commodity capability mapping + rolling baselines.

For each (reporter, hs_code, flow) we compute a trailing 3-year rolling
average (excluding the current year), the % deviation from it, a z-score
against the rolling std, and a blended anomaly score in [0, 1]:

    anomaly_score = 0.6 * clip(deviation_pct / 200, 0, 1)
                  + 0.4 * clip(z_score / 4, 0, 1)        (positive deviations)

So +100% over baseline ≈ 0.3–0.7 depending on volatility; the
material_anomaly signal threshold (score > 0.7 AND deviation > 100%) fires
on large deviations that are also unusual for that series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from stratum.core.text import stable_id


def map_capability(flows: pd.DataFrame, hs_ref: pd.DataFrame) -> pd.DataFrame:
    """Join capability_category/signal_weight onto flows by 4-digit HS prefix."""
    flows = flows.copy()
    flows["hs4"] = flows["hs_code"].astype(str).str[:4]
    ref = hs_ref.copy()
    ref["hs4"] = ref["hs_code"].astype(str).str[:4]
    ref = ref[["hs4", "commodity_name", "capability_category", "signal_weight"]]
    out = flows.merge(ref, on="hs4", how="left")
    out["capability_category"] = out["capability_category"].fillna("uncategorized")
    out["signal_weight"] = out["signal_weight"].fillna(0.3)
    return out.drop(columns=["hs4"])


def annual_with_baselines(
    mapped_flows: pd.DataFrame,
    *,
    window_years: int = 3,
    anomaly_flag_pct: float = 50.0,
) -> pd.DataFrame:
    """Aggregate to (reporter, hs_code, flow, year) and attach baselines.

    Expects columns: reporter_country, hs_code, commodity_name,
    capability_category, signal_weight, flow_direction, trade_value_usd,
    net_weight_kg, year.
    """
    keys = ["reporter_country", "hs_code", "flow_direction"]
    annual = (
        mapped_flows.groupby(keys + ["year"], dropna=False)
        .agg(
            trade_value_usd=("trade_value_usd", "sum"),
            net_weight_kg=("net_weight_kg", "sum"),
            commodity_name=("commodity_name", "first"),
            capability_category=("capability_category", "first"),
            signal_weight=("signal_weight", "first"),
        )
        .reset_index()
        .sort_values(keys + ["year"])
    )

    grouped = annual.groupby(keys, dropna=False)["trade_value_usd"]
    # Trailing window EXCLUDING current year: shift(1) then roll.
    annual["rolling_avg_3y"] = grouped.transform(
        lambda s: s.shift(1).rolling(window_years, min_periods=2).mean()
    )
    annual["rolling_std_3y"] = grouped.transform(
        lambda s: s.shift(1).rolling(window_years, min_periods=2).std()
    )

    base = annual["rolling_avg_3y"]
    annual["baseline_deviation_pct"] = np.where(
        base > 0, (annual["trade_value_usd"] - base) / base * 100.0, np.nan
    )
    std = annual["rolling_std_3y"]
    annual["z_score"] = np.where(
        std > 0, (annual["trade_value_usd"] - base) / std, np.nan
    )

    dev_component = np.clip(annual["baseline_deviation_pct"] / 200.0, 0, 1)
    z_component = np.clip(annual["z_score"] / 4.0, 0, 1)
    # A flat baseline (std == 0) makes any jump maximally unusual — fall back
    # to the deviation component instead of discounting the score.
    z_component = np.where(
        (std > 0) & np.isfinite(annual["z_score"]), z_component, dev_component
    )
    score = 0.6 * dev_component + 0.4 * z_component
    annual["anomaly_score"] = np.where(
        annual["baseline_deviation_pct"] > 0, np.round(score, 4), 0.0
    )
    annual["anomaly_flag"] = annual["baseline_deviation_pct"] > anomaly_flag_pct

    annual["flow_id"] = [
        stable_id(r.reporter_country, r.hs_code, r.flow_direction, r.year, prefix="cf_")
        for r in annual.itertuples(index=False)
    ]
    return annual
