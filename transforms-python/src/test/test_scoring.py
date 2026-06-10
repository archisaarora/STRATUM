import pandas as pd

from stratum.core.features.baselines import annual_with_baselines, map_capability
from stratum.core.scoring.material_credibility import material_credibility
from stratum.core.scoring.procurement_acceleration import procurement_acceleration
from stratum.core.scoring.profiles import country_threat_profiles
from stratum.core.scoring.signals import generate_all_signals
from test.test_features import HS_REF, make_flows


def _spiking_flows() -> pd.DataFrame:
    """IRN propellant imports flat then tripling; FRA and USA stay flat."""
    irn = make_flows([100e6, 100e6, 100e6, 100e6, 320e6], country="IRN")
    fra = make_flows([100e6, 101e6, 99e6, 100e6, 102e6], country="FRA")
    usa = make_flows([50e6, 51e6, 49e6, 50e6, 52e6], country="USA")
    return annual_with_baselines(
        map_capability(pd.concat([irn, fra, usa]), HS_REF))


def _sipri() -> pd.DataFrame:
    rows = []
    for c, v in [("IRN", 10e9), ("FRA", 55e9), ("USA", 800e9)]:
        for y in range(2020, 2025):
            rows.append({"country_code": c, "year": y,
                         "measure": "expenditure_current_usd", "value": v})
    return pd.DataFrame(rows)


def test_material_credibility_underdeclaration():
    cred = material_credibility(_spiking_flows(), _sipri())
    irn = cred[(cred.country_code == "IRN") & (cred.year == 2024)].iloc[0]
    fra = cred[(cred.country_code == "FRA") & (cred.year == 2024)].iloc[0]
    # IRN: high material percentile, low declared percentile => under-declaring
    assert irn["underdeclaration_score"] > 0
    assert irn["credibility_score"] < fra["credibility_score"]


def _classified_contracts() -> pd.DataFrame:
    rows = []
    # 2 hypersonics contracts in the prior window, 8 in the last 12 months
    dates = (["2024-03-01", "2024-05-01"]
             + [f"2025-{m:02d}-01" for m in range(1, 9)])
    for i, d in enumerate(dates):
        rows.append({
            "contract_id": f"c{i}", "recipient_country": "USA",
            "recipient_name": "Lockheed Martin", "award_date": d,
            "total_value_usd": 10e6 if d.startswith("2024") else 40e6,
            "primary_capability_domain": "hypersonics",
            "capability_maturity_stage": "development",
            "threat_relevance_score": 0.8,
        })
    return pd.DataFrame(rows)


def test_procurement_acceleration_fires():
    accel = procurement_acceleration(
        _classified_contracts(), as_of=pd.Timestamp("2025-09-01"))
    row = accel[(accel.country_code == "USA") & (accel.domain == "hypersonics")].iloc[0]
    assert row["domain_acceleration_flag"]
    assert row["contract_count_12m"] == 8
    assert row["tempo_score"] > 0.5


def test_signal_generation_and_compound():
    flows = _spiking_flows()
    sipri = _sipri()
    wb = pd.DataFrame(
        [{"country_code": "IRN", "year": y, "indicator_code": "NY.GDP.MKTP.CD",
          "value": 400e9} for y in range(2020, 2025)]
        + [{"country_code": "IRN", "year": y, "indicator_code": "MS.MIL.XPND.GD.ZS",
            "value": 4.0} for y in range(2020, 2025)]
    )
    from stratum.core.features.budget import budget_discrepancy
    budget = budget_discrepancy(sipri, wb)
    cred = material_credibility(flows, sipri)
    accel = procurement_acceleration(
        _classified_contracts(), as_of=pd.Timestamp("2025-09-01"))

    signals = generate_all_signals(
        flows=flows, accel=accel, budget=budget, credibility=cred, velocity=None)

    types = set(signals["signal_type"])
    assert "material_anomaly" in types
    assert "procurement_acceleration" in types
    assert "budget_discrepancy" in types

    irn_material = signals[(signals.country_code == "IRN")
                           & (signals.signal_type == "material_anomaly")]
    assert len(irn_material) == 1
    assert "propellants_and_explosives" in irn_material.iloc[0]["domain"]

    # IRN: material anomaly + budget discrepancy (wildcard) => compound
    compound = signals[(signals.signal_type == "compound_signal")
                       & (signals.country_code == "IRN")]
    assert len(compound) == 1
    base_ids = set(signals[(signals.country_code == "IRN")
                           & (signals.signal_type != "compound_signal")]["signal_id"])
    assert set(compound.iloc[0]["supporting_evidence"]).issubset(base_ids)
    # escalation multiplier should push compound above the geometric mean
    assert compound.iloc[0]["signal_strength"] >= irn_material.iloc[0]["signal_strength"] * 0.9

    # deterministic IDs => idempotent re-runs
    again = generate_all_signals(
        flows=flows, accel=accel, budget=budget, credibility=cred, velocity=None)
    assert sorted(again["signal_id"]) == sorted(signals["signal_id"])


def test_country_profiles_tiering_and_leadtime():
    flows = _spiking_flows()
    sipri = _sipri()
    cred = material_credibility(flows, sipri)
    accel = procurement_acceleration(
        _classified_contracts(), as_of=pd.Timestamp("2025-09-01"))
    signals = generate_all_signals(
        flows=flows, accel=accel, budget=None, credibility=cred, velocity=None)

    profiles = country_threat_profiles(
        signals, cred, _classified_contracts(), None)
    assert set(profiles["country_code"]) >= {"IRN", "USA"}
    irn = profiles[profiles.country_code == "IRN"].iloc[0]
    assert irn["threat_acceleration_index"] > 0
    assert irn["composite_threat_tier"] in {"S", "A", "B", "C"}
    assert "propellants_and_explosives" in irn["top_domains_of_concern"]

    usa = profiles[profiles.country_code == "USA"].iloc[0]
    assert usa["dominant_maturity_stage"] == "development"
    assert usa["lead_time_min_months"] == 18
    assert usa["lead_time_max_months"] <= 36


def test_report_builder():
    from stratum.core.report import build_report
    flows = _spiking_flows()
    sipri = _sipri()
    cred = material_credibility(flows, sipri)
    signals = generate_all_signals(
        flows=flows, accel=None, budget=None, credibility=cred, velocity=None)
    irn_signals = signals[signals.country_code == "IRN"]
    report = build_report(
        irn_signals,
        country_name="Iran",
        profile={"composite_threat_tier": "A", "threat_acceleration_index": 55.0,
                 "lead_time_min_months": 18, "lead_time_max_months": 36},
        evidence_flows=flows[(flows.reporter_country == "IRN") & (flows.year == 2024)],
    )
    assert "INTELLIGENCE REPORT — IRAN" in report
    for section in ["Executive Summary", "Observed Signals", "Supporting Evidence",
                    "Confidence Assessment", "Recommended Action"]:
        assert f"## {section}" in report
    assert "18–36 months" in report
