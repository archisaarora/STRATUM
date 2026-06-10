"""Intelligence report builder.

Deterministic markdown skeleton for the "Generate Intelligence Report"
workflow. In production the AIP Logic function (docs/03_AIP_SETUP.md)
passes this skeleton plus the evidence rows to an LLM block for the
executive-summary prose; the skeleton alone is already a readable product
(and the fallback if AIP is unavailable).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

SECTION_ORDER = [
    "Executive Summary", "Observed Signals", "Supporting Evidence",
    "Confidence Assessment", "Recommended Action",
]


def build_report(
    signals: pd.DataFrame,
    *,
    country_name: str,
    profile: dict | None = None,
    evidence_flows: pd.DataFrame | None = None,
    evidence_contracts: pd.DataFrame | None = None,
    report_date: str | None = None,
) -> str:
    report_date = report_date or date.today().isoformat()
    s = signals.sort_values("signal_strength", ascending=False)
    domains = sorted({d for d in s["domain"] if d != "defense_general"})
    compound = s[s["signal_type"] == "compound_signal"]

    lines: list[str] = []
    lines.append(f"# INTELLIGENCE REPORT — {country_name.upper()}")
    lines.append(f"*STRATUM automated threat assessment — {report_date} — "
                 f"OSINT-derived, UNCLASSIFIED sources*")
    lines.append("")

    lines.append("## Executive Summary")
    tier = profile.get("composite_threat_tier") if profile else None
    tai = profile.get("threat_acceleration_index") if profile else None
    summary = (
        f"{country_name} presents {len(s)} active threat signal(s)"
        f"{' including ' + str(len(compound)) + ' compound signal(s)' if len(compound) else ''}"
        f" across {', '.join(domains) if domains else 'general defense activity'}."
    )
    if tier is not None:
        summary += (f" Composite threat tier: **{tier}** "
                    f"(threat acceleration index {tai}).")
    if profile and profile.get("lead_time_min_months") is not None:
        summary += (
            f" Estimated lead time to operational capability in the top domain: "
            f"{profile['lead_time_min_months']}–{profile['lead_time_max_months']} months."
        )
    lines.append(summary)
    lines.append("")

    lines.append("## Observed Signals")
    for r in s.itertuples(index=False):
        lines.append(
            f"- **[{r.signal_type}]** ({r.domain}, strength "
            f"{r.signal_strength:.2f}, confidence {r.confidence_score:.2f}) — "
            f"{r.description_text}"
        )
    lines.append("")

    lines.append("## Supporting Evidence")
    n_items = 0
    if evidence_flows is not None and len(evidence_flows):
        lines.append("**Commodity flows:**")
        for r in evidence_flows.head(10).itertuples(index=False):
            lines.append(
                f"- HS {r.hs_code} {r.commodity_name}: "
                f"${r.trade_value_usd:,.0f} in {int(r.year)} "
                f"({r.baseline_deviation_pct:+.0f}% vs 3-yr baseline, "
                f"anomaly {r.anomaly_score:.2f})"
            )
            n_items += 1
    if evidence_contracts is not None and len(evidence_contracts):
        lines.append("**Procurement contracts:**")
        for r in evidence_contracts.head(10).itertuples(index=False):
            desc = str(r.description_raw_text)[:160].replace("\n", " ")
            lines.append(
                f"- {r.award_date} | {r.recipient_name} | "
                f"${(r.total_value_usd or 0):,.0f} | {desc}…"
            )
            n_items += 1
    if n_items == 0:
        lines.append("- Evidence references retained on signal objects "
                     "(see supporting_evidence IDs).")
    lines.append("")

    lines.append("## Confidence Assessment")
    avg_conf = float(s["confidence_score"].mean())
    band = "HIGH" if avg_conf >= 0.75 else "MODERATE" if avg_conf >= 0.5 else "LOW"
    lines.append(
        f"Mean signal confidence {avg_conf:.2f} → **{band}**. All inputs are "
        f"open-source (USASpending, SIPRI, UN Comtrade, World Bank, "
        f"GDELT/ACLED, OpenSanctions); collection gaps and reporting lags "
        f"(~2 months for trade data) apply."
    )
    lines.append("")

    lines.append("## Recommended Action")
    if len(compound):
        lines.append(
            "- Convergent independent indicators warrant analyst escalation and "
            "collection-manager review of the affected domain(s)."
        )
    lines.append("- Validate flagged commodity flows against partner-country "
                 "mirror statistics.")
    lines.append("- Re-run assessment after next monthly trade-data refresh; "
                 "monitor for new compound signals.")
    return "\n".join(lines)
