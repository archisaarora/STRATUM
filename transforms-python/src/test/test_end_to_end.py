"""Full-pipeline integration test on the synthetic scenario.

Drives raw sample data through every core stage exactly as the Foundry
transforms do (the wrappers are thin adapters around these calls) and
asserts the planted storyline comes out the other side:

  IRN  -> material_anomaly + budget_discrepancy -> compound signal
  USA  -> procurement_acceleration (hypersonics)
  MMR  -> arms_transfer_spike
  ETH  -> top conflict intensity
  CHN  -> NO material anomaly (discrimination check)
"""
import pandas as pd

from stratum.core import sample_data
from stratum.core.countries import CountryIndex
from stratum.core.features.arms_velocity import transfer_velocity
from stratum.core.features.baselines import annual_with_baselines, map_capability
from stratum.core.features.budget import budget_discrepancy
from stratum.core.features.conflict import monthly_intensity
from stratum.core.features.contracts import company_rollup, merge_contract_sources
from stratum.core.llm.keyword_classifier import classify
from stratum.core.parsing.opensanctions import build_org_name_index, parse_targets
from stratum.core.parsing.sipri_arms import parse_trade_register
from stratum.core.parsing.sipri_milex import parse_workbook
from stratum.core.report import build_report
from stratum.core.scoring.material_credibility import material_credibility
from stratum.core.scoring.procurement_acceleration import procurement_acceleration
from stratum.core.scoring.profiles import country_threat_profiles
from stratum.core.scoring.signals import generate_all_signals

HS_REF = pd.DataFrame([
    {"hs_code": "3601", "commodity_name": "Propellant powders",
     "capability_category": "propellants_and_explosives", "signal_weight": 1.0},
    {"hs_code": "2814", "commodity_name": "Ammonia",
     "capability_category": "propellants_and_explosives", "signal_weight": 0.7},
    {"hs_code": "8108", "commodity_name": "Titanium",
     "capability_category": "airframe_and_armor_materials", "signal_weight": 0.9},
    {"hs_code": "8542", "commodity_name": "Integrated circuits",
     "capability_category": "guidance_and_electronics", "signal_weight": 0.9},
    {"hs_code": "2710", "commodity_name": "Petroleum oils",
     "capability_category": "fuel_and_logistics", "signal_weight": 0.4},
])


def run_pipeline():
    idx = CountryIndex.from_reference(sample_data.reference_frame())

    # ---- clean layer ----
    milex = parse_workbook(sample_data.sipri_milex_workbook())
    milex, _ = idx.standardize_column(milex, "country_name_raw", "country_code")
    milex = milex[milex["country_code"].notna()]

    arms = parse_trade_register(sample_data.sipri_arms_csv().encode())
    arms, _ = idx.standardize_column(arms, "supplier", "supplier_country")
    arms, _ = idx.standardize_column(arms, "recipient", "recipient_country")

    comtrade = sample_data.comtrade_raw().rename(
        columns={"reporter_iso3": "reporter_country"})
    comtrade["flow_direction"] = "import"

    wb = sample_data.worldbank_raw().rename(columns={"country_iso3": "country_code"})

    gdelt = sample_data.gdelt_raw()
    gdelt["date"] = pd.to_datetime(gdelt["event_date_int"].astype(str))
    gdelt["country_code"] = gdelt["actor1_country"]
    gdelt = (gdelt.groupby(["country_code", "date"])
             .agg(conflict_event_count=("event_count", "sum"),
                  avg_goldstein=("avg_goldstein", "mean")).reset_index())

    acled = sample_data.acled_raw()
    acled, _ = idx.standardize_column(acled, "country", "country_code")

    sanctions = parse_targets(sample_data.opensanctions_csv())

    # ---- features ----
    flows = annual_with_baselines(map_capability(comtrade, HS_REF))
    budget = budget_discrepancy(milex, wb)
    velocity = transfer_velocity(arms)
    conflict = monthly_intensity(gdelt, acled)

    merged = merge_contract_sources(
        sample_data.usaspending_raw().assign(recipient_country="USA"),
        sample_data.dod_contracts_raw().assign(
            contract_date=lambda d: d["announcement_date_text"]),
    )
    cls = merged["description_raw_text"].map(classify)
    merged["primary_capability_domain"] = [c["capability_domains"][0] for c in cls]
    merged["capability_maturity_stage"] = [c["capability_maturity_stage"] for c in cls]
    merged["threat_relevance_score"] = [c["threat_relevance_score"] for c in cls]

    companies = company_rollup(merged, build_org_name_index(sanctions))

    # ---- scores & signals ----
    credibility = material_credibility(flows, milex, merged)
    accel = procurement_acceleration(merged)
    signals = generate_all_signals(
        flows=flows, accel=accel, budget=budget,
        credibility=credibility, velocity=velocity)
    profiles = country_threat_profiles(signals, credibility, merged, conflict)
    return {
        "flows": flows, "budget": budget, "velocity": velocity,
        "conflict": conflict, "merged": merged, "companies": companies,
        "credibility": credibility, "accel": accel,
        "signals": signals, "profiles": profiles, "idx": idx,
    }


def test_full_pipeline_storyline():
    r = run_pipeline()
    signals, profiles = r["signals"], r["profiles"]

    irn = signals[signals.country_code == "IRN"]
    assert "material_anomaly" in set(irn.signal_type)
    assert "budget_discrepancy" in set(irn.signal_type)
    assert "compound_signal" in set(irn.signal_type), (
        "the planted IRN storyline must produce a compound signal")
    compound = irn[irn.signal_type == "compound_signal"].iloc[0]
    assert compound["domain"] == "propellants_and_explosives"

    usa = signals[(signals.country_code == "USA")
                  & (signals.signal_type == "procurement_acceleration")]
    assert len(usa) >= 1
    assert "hypersonics" in set(usa.domain)

    mmr = signals[(signals.country_code == "MMR")
                  & (signals.signal_type == "arms_transfer_spike")]
    assert len(mmr) == 1

    # CHN gentle titanium growth must NOT alarm
    chn = signals[(signals.country_code == "CHN")
                  & (signals.signal_type == "material_anomaly")]
    assert len(chn) == 0

    # profiles: IRN ranks above CHN; tiers populated
    assert set(profiles.country_code) >= {"IRN", "USA", "MMR"}
    irn_p = profiles[profiles.country_code == "IRN"].iloc[0]
    assert irn_p["compound_signal_count"] >= 1
    assert irn_p["composite_threat_tier"] in {"S", "A", "B"}

    # ETH conflict intensity is the hottest
    conflict = r["conflict"]
    last = conflict[conflict["month"] == conflict["month"].max()]
    assert last.sort_values("intensity_score").iloc[-1]["country_code"] == "ETH"

    # sanctions cross-reference catches the planted recipient
    flagged = r["companies"][r["companies"]["opensanctions_match"]]
    assert "aviacon zitotrans" in set(flagged["normalized_name"])


def test_report_generation_from_pipeline():
    r = run_pipeline()
    signals, profiles, flows = r["signals"], r["profiles"], r["flows"]
    irn_signals = signals[signals.country_code == "IRN"]
    profile = profiles[profiles.country_code == "IRN"].iloc[0].to_dict()
    report = build_report(
        irn_signals, country_name=r["idx"].name_of("IRN"), profile=profile,
        evidence_flows=flows[(flows.reporter_country == "IRN")
                             & (flows.anomaly_flag)],
    )
    assert "COMPOUND SIGNAL" in report
    assert "## Recommended Action" in report
    assert "Iran" in report.splitlines()[0].title()
