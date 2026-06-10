"""Skipped-source behavior: placeholder (header-only) uploads must flow
through cleanly as empty frames, and UCDP GED must convert to the ACLED
shape so it can substitute when ACLED registration isn't available."""
import pandas as pd

from stratum.core.features.arms_velocity import transfer_velocity
from stratum.core.features.conflict import monthly_intensity
from stratum.core.parsing.sipri_arms import parse_trade_register
from stratum.core.parsing.ucdp import parse_ged_to_acled_shape
from stratum.core.scoring.signals import generate_all_signals

REGISTER_HEADER = (
    "Supplier,Recipient,Year of order,Number ordered,Weapon designation,"
    "Weapon description,Number delivered,Year(s) of delivery,Status,"
    "SIPRI TIV per unit,SIPRI TIV for total order\n")


def test_placeholder_register_parses_empty():
    df = parse_trade_register(REGISTER_HEADER.encode())
    assert len(df) == 0
    assert "supplier" in df.columns and "total_tiv" in df.columns


def test_velocity_handles_empty_input():
    empty = parse_trade_register(REGISTER_HEADER.encode())
    empty = empty.rename(columns={"recipient": "recipient_country"})
    out = transfer_velocity(empty)
    assert len(out) == 0


def test_conflict_intensity_handles_empty_inputs():
    out = monthly_intensity(
        pd.DataFrame(columns=["country_code", "date", "conflict_event_count",
                              "avg_goldstein"]),
        pd.DataFrame(columns=["country_code", "event_date", "fatalities"]))
    assert len(out) == 0
    assert "intensity_score" in out.columns


def test_signals_with_only_material_inputs():
    """No arms, no conflict, no contracts, no budget — material-only run."""
    from stratum.core.features.baselines import annual_with_baselines, map_capability
    from test.test_features import HS_REF, make_flows

    flows = annual_with_baselines(
        map_capability(make_flows([100e6, 100e6, 100e6, 100e6, 320e6]), HS_REF))
    signals = generate_all_signals(
        flows=flows, accel=None, budget=None, credibility=None, velocity=None)
    assert set(signals["signal_type"]) == {"material_anomaly"}
    assert len(signals) == 1


GED_CSV = """id,year,type_of_violence,conflict_name,date_start,date_end,side_a,side_b,adm_1,latitude,longitude,country,best,source_headline
401234,2024,1,Ethiopia: Government,2024-03-05,2024-03-06,Government of Ethiopia,Fano,Amhara,11.6,37.4,Ethiopia,14,clash reported
401235,2024,3,Myanmar one-sided,2024-04-10,2024-04-10,Military of Myanmar,Civilians,Sagaing,22.0,95.0,Myanmar,6,village raid
"""


def test_ucdp_ged_converts_to_acled_shape():
    out = parse_ged_to_acled_shape(GED_CSV)
    assert len(out) == 2
    row = out.iloc[0]
    assert row["event_id_cnty"] == "GED401234"
    assert row["event_date"] == "2024-03-05"
    assert row["event_type"] == "State-based conflict"
    assert row["country"] == "Ethiopia"
    assert row["fatalities"] == 14
    # exact column compatibility with the raw_acled_events dataset
    expected = {"event_id_cnty", "event_date", "year", "event_type",
                "sub_event_type", "country", "admin1", "location", "latitude",
                "longitude", "actor1", "actor2", "fatalities", "notes", "source"}
    assert set(out.columns) == expected


def test_ucdp_events_drive_conflict_intensity():
    events = parse_ged_to_acled_shape(GED_CSV)
    events["country_code"] = events["country"].map(
        {"Ethiopia": "ETH", "Myanmar": "MMR"})
    out = monthly_intensity(None, events)
    assert set(out["country_code"]) == {"ETH", "MMR"}
    eth = out[out.country_code == "ETH"].iloc[0]
    assert eth["intensity_score"] > 0
