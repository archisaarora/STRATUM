"""Transform 4.1 core — Material Credibility Score.

For each (country, domain, year):

  material_signal  — anomaly-weighted, signal-weighted import value for
                     commodity flows mapped to the domain
  declared_signal  — SIPRI declared milex (per-country scale anchor)
                     plus LLM-classified contract spend in the domain

Both are converted to cross-country percentiles within (domain, year), so
the discrepancy compares each country's *relative standing* on physical
evidence vs. declared programs:

  underdeclaration_score = clip(material_pctile - declared_pctile, 0, 1) * 100
  overdeclaration_score  = clip(declared_pctile - material_pctile, 0, 1) * 100
  credibility_score      = 100 - max(under, over)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def material_credibility(
    flows_with_baselines: pd.DataFrame,  # feature_comtrade_with_baselines
    sipri_milex: pd.DataFrame,           # clean (long): country_code, year, measure, value
    classified_contracts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    imports = flows_with_baselines[
        (flows_with_baselines["flow_direction"] == "import")
        & (flows_with_baselines["capability_category"] != "uncategorized")
    ].copy()
    if imports.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    # Material evidence: import value boosted by anomaly score, weighted by
    # how defense-specific the commodity is.
    imports["weighted_value"] = (
        imports["trade_value_usd"].fillna(0)
        * imports["signal_weight"].fillna(0.3)
        * (1.0 + imports["anomaly_score"].fillna(0))
    )
    material = (
        imports.groupby(["reporter_country", "capability_category", "year"])
        ["weighted_value"].sum().reset_index()
        .rename(columns={
            "reporter_country": "country_code",
            "capability_category": "domain",
            "weighted_value": "material_signal",
        })
    )

    milex = (
        sipri_milex[sipri_milex["measure"] == "expenditure_current_usd"]
        [["country_code", "year", "value"]]
        .rename(columns={"value": "milex_usd"})
    )
    df = material.merge(milex, on=["country_code", "year"], how="left")
    df["declared_signal"] = df["milex_usd"].fillna(0)
    df["contract_spend"] = 0.0  # stable schema even when no contracts exist

    if classified_contracts is not None and len(classified_contracts):
        c = classified_contracts.copy()
        c = c[c["primary_capability_domain"].notna()
              & (c["primary_capability_domain"] != "none")]
        c["year"] = pd.to_datetime(c["award_date"], errors="coerce").dt.year
        contract_spend = (
            c.groupby(["recipient_country", "primary_capability_domain", "year"])
            ["total_value_usd"].sum().reset_index()
            .rename(columns={
                "recipient_country": "country_code",
                "primary_capability_domain": "domain",
                "total_value_usd": "contract_spend_add",
            })
        )
        df = df.merge(contract_spend, on=["country_code", "domain", "year"], how="left")
        df["contract_spend"] = df["contract_spend_add"].fillna(0)
        df = df.drop(columns=["contract_spend_add"])
        df["declared_signal"] = df["declared_signal"] + df["contract_spend"]

    by = df.groupby(["domain", "year"])
    df["material_pctile"] = by["material_signal"].rank(pct=True)
    df["declared_pctile"] = by["declared_signal"].rank(pct=True)

    gap = df["material_pctile"] - df["declared_pctile"]
    df["underdeclaration_score"] = (np.clip(gap, 0, 1) * 100).round(2)
    df["overdeclaration_score"] = (np.clip(-gap, 0, 1) * 100).round(2)
    df["credibility_score"] = (
        100 - df[["underdeclaration_score", "overdeclaration_score"]].max(axis=1)
    ).round(2)
    return df[OUTPUT_COLUMNS]


OUTPUT_COLUMNS = [
    "country_code", "domain", "year", "material_signal", "milex_usd",
    "contract_spend", "declared_signal", "material_pctile", "declared_pctile",
    "underdeclaration_score", "overdeclaration_score", "credibility_score",
]
