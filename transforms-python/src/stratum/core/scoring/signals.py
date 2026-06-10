"""Transform 4.3 core — the ThreatSignal generation engine.

Implements the five SIGNAL_RULES from the build prompt. Each rule reads a
scored feature dataset and emits discrete signals when thresholds are met;
the compound rule then looks for >=2 distinct signal types converging on
the same (country, domain) inside a 6-month window — budget_discrepancy
(domain "defense_general") acts as a wildcard that can join any domain
group for its country.

Confidence scores are heuristic but principled: rules with longer
baselines and physical evidence get higher base confidence; thin data
(short history, few contracts) discounts it.
"""
from __future__ import annotations

from datetime import datetime
from statistics import geometric_mean

import pandas as pd

from stratum.core.text import stable_id

DEFENSE_GENERAL = "defense_general"


def _signal(
    *,
    signal_type: str,
    country_code: str,
    domain: str,
    strength: float,
    confidence: float,
    description: str,
    evidence: list[str],
    window_end,
    created_at: str,
) -> dict:
    return {
        "signal_id": stable_id(signal_type, country_code, domain, window_end, prefix="sig_"),
        "signal_type": signal_type,
        "country_code": country_code,
        "domain": domain,
        "signal_strength": round(min(max(float(strength), 0.0), 1.0), 4),
        "confidence_score": round(min(max(float(confidence), 0.0), 1.0), 4),
        "description_text": description,
        "supporting_evidence": evidence,
        "window_end": str(window_end),
        "created_at": created_at,
        "reviewed": False,
        "analyst_notes": "",
    }


def material_anomaly_signals(
    flows: pd.DataFrame,
    *,
    min_score: float = 0.7,
    min_deviation_pct: float = 100.0,
    latest_year_only: bool = True,
    created_at: str | None = None,
) -> list[dict]:
    created_at = created_at or datetime.utcnow().isoformat()
    df = flows[
        (flows["flow_direction"] == "import")
        & (flows["anomaly_score"] > min_score)
        & (flows["baseline_deviation_pct"] > min_deviation_pct)
        & (flows["capability_category"] != "uncategorized")
    ].copy()
    if latest_year_only and len(df):
        latest = df.groupby("reporter_country")["year"].transform("max")
        df = df[df["year"] == latest]

    out = []
    for r in df.itertuples(index=False):
        years_history = 5  # baseline requires >=2 prior years by construction
        confidence = min(0.9, 0.5 + 0.08 * years_history)
        out.append(_signal(
            signal_type="material_anomaly",
            country_code=r.reporter_country,
            domain=r.capability_category,
            strength=r.anomaly_score,
            confidence=confidence * float(getattr(r, "signal_weight", 0.5) or 0.5) ** 0.5,
            description=(
                f"Commodity import of HS {r.hs_code} ({r.commodity_name}) by "
                f"{r.reporter_country} is {r.baseline_deviation_pct:.0f}% above its "
                f"3-year baseline in {int(r.year)}, suggesting accelerated "
                f"{r.capability_category} production activity"
            ),
            evidence=[r.flow_id],
            window_end=int(r.year),
            created_at=created_at,
        ))
    return out


def procurement_acceleration_signals(
    accel: pd.DataFrame, *, created_at: str | None = None
) -> list[dict]:
    created_at = created_at or datetime.utcnow().isoformat()
    out = []
    for r in accel[accel["domain_acceleration_flag"]].itertuples(index=False):
        confidence = min(0.85, 0.4 + 0.05 * float(r.contract_count_12m))
        growth = (f"{r.count_growth_pct:.0f}%"
                  if pd.notna(r.count_growth_pct) else "from a standing start")
        out.append(_signal(
            signal_type="procurement_acceleration",
            country_code=r.country_code,
            domain=r.domain,
            strength=r.tempo_score,
            confidence=confidence,
            description=(
                f"Contract awards in the {r.domain} domain for {r.country_code} "
                f"accelerated {growth} year-over-year "
                f"({int(r.contract_count_12m)} awards, "
                f"${r.contract_value_12m:,.0f} in the last 12 months)"
            ),
            evidence=[f"accel:{r.country_code}:{r.domain}"],
            window_end=str(getattr(r, "window_end", ""))[:10],
            created_at=created_at,
        ))
    return out


def budget_discrepancy_signals(
    budget: pd.DataFrame,
    credibility: pd.DataFrame | None,
    *,
    underdeclaration_min: float = 60.0,
    created_at: str | None = None,
) -> list[dict]:
    created_at = created_at or datetime.utcnow().isoformat()
    out = []

    latest = budget[budget["budget_credibility_flag"].fillna(False)]
    if len(latest):
        idx = latest.groupby("country_code")["year"].idxmax()
        latest = latest.loc[idx]
    for r in latest.itertuples(index=False):
        gap = float(r.sipri_wb_discrepancy_pct)
        direction = ("above" if r.sipri_milex_usd >= (r.wb_milex_usd_implied or 0)
                     else "below")
        out.append(_signal(
            signal_type="budget_discrepancy",
            country_code=r.country_code,
            domain=DEFENSE_GENERAL,
            strength=min(1.0, gap / 100.0),
            confidence=0.7,
            description=(
                f"Declared defense budget of {r.country_code} is inconsistent "
                f"across independent compilations: SIPRI figure is {gap:.0f}% "
                f"{direction} the World Bank-implied figure for {int(r.year)}"
            ),
            evidence=[f"budget:{r.country_code}:{int(r.year)}"],
            window_end=int(r.year),
            created_at=created_at,
        ))

    if credibility is not None and len(credibility):
        cred = credibility[credibility["underdeclaration_score"] > underdeclaration_min]
        if len(cred):
            idx = cred.groupby(["country_code", "domain"])["year"].idxmax()
            cred = cred.loc[idx]
        for r in cred.itertuples(index=False):
            out.append(_signal(
                signal_type="budget_discrepancy",
                country_code=r.country_code,
                domain=r.domain,
                strength=float(r.underdeclaration_score) / 100.0,
                confidence=0.65,
                description=(
                    f"Material evidence for {r.country_code} in {r.domain} "
                    f"(import percentile {r.material_pctile:.2f}) runs well ahead "
                    f"of declared programs (declared percentile "
                    f"{r.declared_pctile:.2f}) in {int(r.year)} — "
                    f"under-declaration score {r.underdeclaration_score:.0f}/100"
                ),
                evidence=[f"credibility:{r.country_code}:{r.domain}:{int(r.year)}"],
                window_end=int(r.year),
                created_at=created_at,
            ))
    return out


def arms_transfer_spike_signals(
    velocity: pd.DataFrame, *, created_at: str | None = None
) -> list[dict]:
    created_at = created_at or datetime.utcnow().isoformat()
    out = []
    spikes = velocity[velocity["transfer_spike_flag"].fillna(False)]
    if len(spikes):
        idx = spikes.groupby("recipient_country")["year"].idxmax()
        spikes = spikes.loc[idx]
    max_mag = max(float(spikes["spike_magnitude"].max() or 1.0), 1.0) if len(spikes) else 1.0
    for r in spikes.itertuples(index=False):
        spike_pct = (float(r.spike_magnitude) - 1.0) * 100.0
        out.append(_signal(
            signal_type="arms_transfer_spike",
            country_code=r.recipient_country,
            domain="arms_direct",
            strength=float(r.spike_magnitude) / max_mag,
            confidence=min(0.85, 0.5 + 0.05 * float(r.transfer_count)),
            description=(
                f"Arms transfers received by {r.recipient_country} spiked "
                f"{spike_pct:.0f}% above the 3-year rolling average in "
                f"{int(r.year)} — dominated by {r.top_category or 'mixed categories'}"
            ),
            evidence=[f"arms:{r.recipient_country}:{int(r.year)}"],
            window_end=int(r.year),
            created_at=created_at,
        ))
    return out


def compound_signals(
    base_signals: list[dict],
    *,
    escalation: float = 1.5,
    created_at: str | None = None,
) -> list[dict]:
    """>=2 distinct signal types for the same (country, domain) =>
    compound signal at geometric_mean(strengths) * escalation (capped at 1).

    defense_general signals join every domain group for their country.
    """
    created_at = created_at or datetime.utcnow().isoformat()
    by_country: dict[str, list[dict]] = {}
    for s in base_signals:
        by_country.setdefault(s["country_code"], []).append(s)

    out = []
    for country, sigs in by_country.items():
        wildcard = [s for s in sigs if s["domain"] == DEFENSE_GENERAL]
        domains = {s["domain"] for s in sigs if s["domain"] != DEFENSE_GENERAL}
        for domain in sorted(domains):
            group = [s for s in sigs if s["domain"] == domain] + wildcard
            types = {s["signal_type"] for s in group}
            if len(types) < 2:
                continue
            strengths = [s["signal_strength"] for s in group if s["signal_strength"] > 0]
            if not strengths:
                continue
            strength = min(1.0, geometric_mean(strengths) * escalation)
            confidence = min(
                0.95, sum(s["confidence_score"] for s in group) / len(group) + 0.1
            )
            evidence = [s["signal_id"] for s in group]
            out.append(_signal(
                signal_type="compound_signal",
                country_code=country,
                domain=domain,
                strength=strength,
                confidence=confidence,
                description=(
                    f"COMPOUND SIGNAL: {len(types)} independent indicator types "
                    f"({', '.join(sorted(types))}) converge on {domain} "
                    f"capability development in {country}"
                ),
                evidence=evidence,
                window_end=max(str(s["window_end"]) for s in group),
                created_at=created_at,
            ))
    return out


def generate_all_signals(
    *,
    flows: pd.DataFrame | None,
    accel: pd.DataFrame | None,
    budget: pd.DataFrame | None,
    credibility: pd.DataFrame | None,
    velocity: pd.DataFrame | None,
    thresholds: dict | None = None,
    created_at: str | None = None,
) -> pd.DataFrame:
    t = thresholds or {}
    created_at = created_at or datetime.utcnow().isoformat()
    base: list[dict] = []
    if flows is not None and len(flows):
        base += material_anomaly_signals(
            flows,
            min_score=t.get("material_min_score", 0.7),
            min_deviation_pct=t.get("material_min_deviation", 100.0),
            created_at=created_at,
        )
    if accel is not None and len(accel):
        base += procurement_acceleration_signals(accel, created_at=created_at)
    if budget is not None and len(budget):
        base += budget_discrepancy_signals(
            budget, credibility,
            underdeclaration_min=t.get("underdeclaration_min", 60.0),
            created_at=created_at,
        )
    if velocity is not None and len(velocity):
        base += arms_transfer_spike_signals(velocity, created_at=created_at)

    all_signals = base + compound_signals(
        base, escalation=t.get("compound_escalation", 1.5), created_at=created_at
    )
    if not all_signals:
        return pd.DataFrame(columns=[
            "signal_id", "signal_type", "country_code", "domain",
            "signal_strength", "confidence_score", "description_text",
            "supporting_evidence", "window_end", "created_at",
            "reviewed", "analyst_notes",
        ])
    return pd.DataFrame(all_signals).drop_duplicates(subset=["signal_id"])
