"""Import-intensity forensics — the "under the radar" detector.

Hostile programs rarely import finished weapons (HS 93, warships,
combat aircraft): those are visible and embargoed. They import
*precursors* — propellant chemicals, titanium, ferroalloys, guidance
electronics — which look like ordinary industrial trade. This module
quantifies that pattern per (country, year):

  intensity_ratio       defense-relevant imports / declared milex.
                        A country importing $1 of defense-relevant goods
                        per $10 of declared budget behaves differently
                        from one importing $1 per $1.
  intensity_z           how unusual that ratio is vs all countries that
                        year (z-score of log ratio).
  dual_use_value /      defense-relevant imports split into direct
  direct_value          military goods vs dual-use precursors.
  dual_use_yoy_pct /    growth of each stream — the forensic core.
  direct_yoy_pct
  covert_acquisition_flag
        dual-use imports grew >50% YoY while direct military imports
        stayed flat (<10% growth or absent) AND the country's import
        intensity is elevated vs peers or vs its own history. The
        signature of capability acquisition outside declared channels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DIRECT_CATEGORIES = {"arms_direct", "aircraft_direct", "naval_direct"}

OUTPUT_COLUMNS = [
    "country_code", "year", "defense_import_value", "direct_value",
    "dual_use_value", "dual_use_share", "milex_usd", "intensity_ratio",
    "intensity_z", "ratio_change_pct", "direct_yoy_pct", "dual_use_yoy_pct",
    "top_dual_use_category", "top_dual_use_growth_pct",
    "covert_acquisition_flag",
]


def import_intensity(
    flows_with_baselines: pd.DataFrame,
    sipri_milex: pd.DataFrame,
    *,
    dual_use_growth_min: float = 50.0,
    direct_growth_max: float = 10.0,
    min_peers_for_z: int = 4,
) -> pd.DataFrame:
    imports = flows_with_baselines[
        (flows_with_baselines["flow_direction"] == "import")
        & (flows_with_baselines["capability_category"] != "uncategorized")
    ].copy()
    if imports.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    imports["is_direct"] = imports["capability_category"].isin(DIRECT_CATEGORIES)

    by_cy = (
        imports.groupby(["reporter_country", "year"])
        .apply(_aggregate_country_year, include_groups=False)
        .reset_index()
        .rename(columns={"reporter_country": "country_code"})
        .sort_values(["country_code", "year"])
    )

    milex = (
        sipri_milex[sipri_milex["measure"] == "expenditure_current_usd"]
        [["country_code", "year", "value"]].rename(columns={"value": "milex_usd"})
    )
    df = by_cy.merge(milex, on=["country_code", "year"], how="left")
    df["intensity_ratio"] = np.where(
        df["milex_usd"] > 0, df["defense_import_value"] / df["milex_usd"], np.nan)

    # Peer comparison: z-score of log-ratio within each year.
    df["_log_ratio"] = np.log10(df["intensity_ratio"].where(df["intensity_ratio"] > 0))
    by_year = df.groupby("year")["_log_ratio"]
    mean, std, n = (by_year.transform("mean"), by_year.transform("std"),
                    by_year.transform("count"))
    df["intensity_z"] = np.where(
        (std > 0) & (n >= min_peers_for_z),
        (df["_log_ratio"] - mean) / std, np.nan)
    df = df.drop(columns=["_log_ratio"])

    # Own-history dynamics.
    g = df.groupby("country_code")
    for col, out in [("intensity_ratio", "ratio_change_pct"),
                     ("direct_value", "direct_yoy_pct"),
                     ("dual_use_value", "dual_use_yoy_pct")]:
        prev = g[col].shift(1)
        df[out] = np.where(prev > 0, (df[col] - prev) / prev * 100.0, np.nan)

    direct_flat = (df["direct_yoy_pct"].fillna(0) < direct_growth_max) | \
                  (df["direct_value"].fillna(0) == 0)
    elevated = (df["intensity_z"].fillna(0) > 1.0) | \
               (df["ratio_change_pct"].fillna(0) > 50.0)
    df["covert_acquisition_flag"] = (
        (df["dual_use_yoy_pct"] > dual_use_growth_min) & direct_flat & elevated)
    return df[OUTPUT_COLUMNS]


def _aggregate_country_year(group: pd.DataFrame) -> pd.Series:
    direct = float(group.loc[group["is_direct"], "trade_value_usd"].sum())
    dual = float(group.loc[~group["is_direct"], "trade_value_usd"].sum())
    total = direct + dual
    dual_rows = group[~group["is_direct"]]
    top_cat, top_growth = None, np.nan
    if len(dual_rows):
        cat_value = dual_rows.groupby("capability_category").agg(
            value=("trade_value_usd", "sum"),
            deviation=("baseline_deviation_pct", "max"))
        top_cat = cat_value["value"].idxmax()
        top_growth = float(cat_value.loc[top_cat, "deviation"])
    return pd.Series({
        "defense_import_value": total,
        "direct_value": direct,
        "dual_use_value": dual,
        "dual_use_share": (dual / total) if total > 0 else np.nan,
        "top_dual_use_category": top_cat,
        "top_dual_use_growth_pct": top_growth,
    })
