"""Transform 4.4 core — country threat profiles.

Aggregates active signals per country into:
  threat_acceleration_index (0–100), capability_credibility_score,
  composite tier (S/A/B/C), top domains of concern, lead-time estimate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TYPE_WEIGHTS = {
    "compound_signal": 1.6,
    "covert_acquisition": 1.2,
    "material_anomaly": 1.0,
    "procurement_acceleration": 0.9,
    "arms_transfer_spike": 0.9,
    "budget_discrepancy": 0.7,
    "conflict_correlation": 0.6,
}


def country_threat_profiles(
    signals: pd.DataFrame,
    credibility: pd.DataFrame | None,
    classified_contracts: pd.DataFrame | None,
    conflict_monthly: pd.DataFrame | None,
    *,
    tier_s: float = 75.0,
    tier_a: float = 50.0,
    tier_b: float = 25.0,
    lead_time_bands: dict[str, tuple[int, int]] | None = None,
    as_of: str | None = None,
) -> pd.DataFrame:
    lead_time_bands = lead_time_bands or {
        "research": (36, 72), "development": (18, 36),
        "production": (6, 18), "sustainment": (6, 18), "unknown": (18, 72),
    }
    as_of = as_of or pd.Timestamp.now("UTC").isoformat()

    if signals is None or signals.empty:
        return pd.DataFrame(columns=_PROFILE_COLUMNS)

    sig = signals.copy()
    sig["weight"] = sig["signal_type"].map(TYPE_WEIGHTS).fillna(0.8)
    sig["weighted_strength"] = (
        sig["signal_strength"] * sig["confidence_score"] * sig["weight"]
    )

    rows = []
    for country, g in sig.groupby("country_code"):
        raw = float(g["weighted_strength"].sum())
        # Saturating map: one strong compound ~ 40; several independents -> 70+
        tai = float(np.round(100.0 * (1.0 - np.exp(-raw / 2.5)), 2))

        domain_rank = (
            g[g["domain"] != "defense_general"]
            .groupby("domain")["weighted_strength"].sum()
            .sort_values(ascending=False)
        )
        top_domains = domain_rank.head(3).index.tolist()

        cred_score = None
        if credibility is not None and len(credibility):
            c = credibility[credibility["country_code"] == country]
            if len(c):
                latest_year = c["year"].max()
                cred_score = float(c[c["year"] == latest_year]["credibility_score"].mean())

        stage, lead_lo, lead_hi = _lead_time(
            country, top_domains[0] if top_domains else None,
            classified_contracts, lead_time_bands,
        )
        # Acceleration tempo compresses the estimate toward the lower bound.
        tempo = float(g[g["signal_type"] == "procurement_acceleration"]["signal_strength"].max()) \
            if (g["signal_type"] == "procurement_acceleration").any() else 0.0
        lead_hi_adj = int(round(lead_hi - (lead_hi - lead_lo) * 0.5 * tempo))

        active_conflict = False
        if conflict_monthly is not None and len(conflict_monthly):
            cm = conflict_monthly[conflict_monthly["country_code"] == country]
            if len(cm):
                last = cm.sort_values("month").iloc[-1]
                active_conflict = bool(last["intensity_score"] >= 0.7)

        tier = ("S" if tai >= tier_s else "A" if tai >= tier_a
                else "B" if tai >= tier_b else "C")
        rows.append({
            "country_code": country,
            "threat_acceleration_index": tai,
            "capability_credibility_score": (
                round(cred_score, 2) if cred_score is not None else None),
            "composite_threat_tier": tier,
            "top_domains_of_concern": top_domains,
            "active_signal_count": int(len(g)),
            "compound_signal_count": int((g["signal_type"] == "compound_signal").sum()),
            "dominant_maturity_stage": stage,
            "lead_time_min_months": int(lead_lo),
            "lead_time_max_months": int(lead_hi_adj),
            "active_conflict": active_conflict,
            "last_signal_window": str(g["window_end"].max()),
            "last_updated": as_of,
        })

    return (
        pd.DataFrame(rows, columns=_PROFILE_COLUMNS)
        .sort_values("threat_acceleration_index", ascending=False)
        .reset_index(drop=True)
    )


def _lead_time(
    country: str,
    top_domain: str | None,
    classified: pd.DataFrame | None,
    bands: dict[str, tuple[int, int]],
) -> tuple[str, int, int]:
    stage = "unknown"
    if classified is not None and len(classified) and top_domain:
        c = classified[
            (classified["recipient_country"] == country)
            & (classified["primary_capability_domain"] == top_domain)
        ]
        stages = c["capability_maturity_stage"].dropna()
        stages = stages[stages != "unknown"]
        if len(stages):
            stage = stages.value_counts().index[0]
    lo, hi = bands.get(stage, bands["unknown"])
    return stage, lo, hi


_PROFILE_COLUMNS = [
    "country_code", "threat_acceleration_index", "capability_credibility_score",
    "composite_threat_tier", "top_domains_of_concern", "active_signal_count",
    "compound_signal_count", "dominant_maturity_stage", "lead_time_min_months",
    "lead_time_max_months", "active_conflict", "last_signal_window", "last_updated",
]
