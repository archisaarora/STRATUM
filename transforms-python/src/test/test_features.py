import numpy as np
import pandas as pd

from stratum.core.features.arms_velocity import transfer_velocity
from stratum.core.features.baselines import annual_with_baselines, map_capability
from stratum.core.features.budget import budget_discrepancy
from stratum.core.features.conflict import monthly_intensity
from stratum.core.features.contracts import company_rollup, merge_contract_sources

HS_REF = pd.DataFrame([
    {"hs_code": "3601", "commodity_name": "Propellant powders",
     "capability_category": "propellants_and_explosives", "signal_weight": 1.0},
    {"hs_code": "8108", "commodity_name": "Titanium",
     "capability_category": "airframe_and_armor_materials", "signal_weight": 0.9},
])


def make_flows(values: list[float], hs: str = "3601", country: str = "IRN") -> pd.DataFrame:
    return pd.DataFrame({
        "reporter_country": country,
        "partner_country": "WLD",
        "hs_code": hs,
        "flow_direction": "import",
        "trade_value_usd": values,
        "net_weight_kg": [v / 10 for v in values],
        "year": list(range(2020, 2020 + len(values))),
    })


def test_capability_mapping_and_default():
    flows = pd.concat([make_flows([100.0]), make_flows([50.0], hs="9999")])
    mapped = map_capability(flows, HS_REF)
    cats = dict(zip(mapped["hs_code"], mapped["capability_category"]))
    assert cats["3601"] == "propellants_and_explosives"
    assert cats["9999"] == "uncategorized"


def test_baseline_spike_detection():
    # Flat 100/yr for 4 years then 300 (=> +200% vs trailing avg)
    flows = map_capability(make_flows([100, 100, 100, 100, 300]), HS_REF)
    out = annual_with_baselines(flows)
    last = out[out["year"] == 2024].iloc[0]
    assert last["rolling_avg_3y"] == 100
    assert round(last["baseline_deviation_pct"]) == 200
    assert last["anomaly_flag"]
    assert last["anomaly_score"] > 0.7
    # Early years (insufficient history) must not produce scores
    first = out[out["year"] == 2020].iloc[0]
    assert pd.isna(first["rolling_avg_3y"])
    assert first["anomaly_score"] == 0.0


def test_baseline_no_false_positive_on_flat_series():
    flows = map_capability(make_flows([100, 101, 99, 100, 102]), HS_REF)
    out = annual_with_baselines(flows)
    assert not out[out["year"] == 2024].iloc[0]["anomaly_flag"]


def test_budget_discrepancy_flags_gap():
    sipri = pd.DataFrame([
        {"country_code": "IRN", "year": y, "measure": "expenditure_current_usd",
         "value": v}
        for y, v in [(2020, 10e9), (2021, 10e9), (2022, 10.5e9),
                     (2023, 10.5e9), (2024, 11e9), (2025, 11e9)]
    ])
    wb = pd.DataFrame(
        [{"country_code": "IRN", "year": y, "indicator_code": "NY.GDP.MKTP.CD",
          "value": 400e9} for y in range(2020, 2026)]
        + [{"country_code": "IRN", "year": y, "indicator_code": "MS.MIL.XPND.GD.ZS",
            "value": 4.0} for y in range(2020, 2026)]  # implies 16B vs 11B declared
    )
    out = budget_discrepancy(sipri, wb)
    last = out[out["year"] == 2025].iloc[0]
    assert last["wb_milex_usd_implied"] == 16e9
    assert last["budget_credibility_flag"]
    assert round(last["declared_cagr_5y_pct"], 1) == round(((11 / 10) ** 0.2 - 1) * 100, 1)


def test_arms_velocity_spike():
    transfers = pd.DataFrame([
        {"transfer_id": f"t{i}", "supplier_country": "RUS",
         "recipient_country": "MMR", "weapon_description": "FGA aircraft",
         "order_year": y, "delivery_year_last": y, "total_tiv": tiv}
        for i, (y, tiv) in enumerate(
            [(2020, 50), (2021, 50), (2022, 60), (2023, 55), (2024, 400)])
    ])
    out = transfer_velocity(transfers)
    last = out[out["year"] == 2024].iloc[0]
    assert last["transfer_spike_flag"]
    assert last["spike_magnitude"] > 2
    assert not out[out["year"] == 2023].iloc[0]["transfer_spike_flag"]


def test_conflict_intensity_ranks_hotspot_highest():
    months = pd.date_range("2025-01-01", periods=3, freq="MS")
    gdelt = pd.DataFrame([
        {"country_code": c, "date": m, "conflict_event_count": n, "avg_goldstein": g}
        for m in months
        for c, n, g in [("ETH", 500, -7.0), ("FRA", 10, 2.0), ("BRA", 30, 0.0)]
    ])
    acled = pd.DataFrame([
        {"country_code": "ETH", "event_date": m, "fatalities": 100} for m in months
    ])
    out = monthly_intensity(gdelt, acled)
    last_month = out[out["month"] == months[-1]].set_index("country_code")
    assert last_month.loc["ETH", "intensity_score"] > last_month.loc["FRA", "intensity_score"]
    assert last_month.loc["ETH", "intensity_score"] > 0.8


def test_contract_merge_and_company_rollup():
    usas = pd.DataFrame([{
        "award_id": "CONT_AWD_1", "recipient_name": "Lockheed Martin Corp.",
        "recipient_country": "USA", "awarding_agency_name": "Department of Defense",
        "period_of_performance_start_date": "2025-03-01",
        "total_obligated_amount": 5_000_000,
        "award_description": "Hypersonic glide vehicle thermal protection system research"
        " and development effort phase II",
        "naics_code": "336414", "product_or_service_code": "AC13",
    }])
    dod = pd.DataFrame([{
        "contract_id": "dod_abc", "contractor_name": "Lockheed Martin Corp",
        "contract_date": "2025-04-02", "contract_value_usd": 9_000_000,
        "description_text": "Production of hypersonic missile airframes and "
        "associated scramjet propulsion test articles for the Air Force",
        "contracting_command": "Air Force",
    }])
    merged = merge_contract_sources(usas, dod)
    assert len(merged) == 2
    assert set(merged["source"]) == {"usaspending", "dod"}

    merged["primary_capability_domain"] = "hypersonics"
    merged["threat_relevance_score"] = 0.8
    companies = company_rollup(merged, sanctioned_org_names={"lockheed martin"})
    assert len(companies) == 1  # Corp. vs Corp normalize to the same company
    row = companies.iloc[0]
    assert row["contract_count"] == 2
    assert row["opensanctions_match"]
    assert row["total_contract_value_usd"] == 14_000_000
