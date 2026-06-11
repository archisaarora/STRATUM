"""SIPRI TIV-table CSV exports (the format armstransfers.sipri.org
actually produces for 'imported weapons by country' downloads)."""
import pandas as pd
import pytest

from stratum.core.features.arms_velocity import transfer_velocity
from stratum.core.parsing.sipri_arms import parse_tiv_csv

BANNER = (
    "Volume of transfers of major arms\n"
    "Figures are in millions of SIPRI trend-indicator values (TIVs).\n"
    "Source: SIPRI Arms Transfers Database (c) SIPRI.\n"
    "Data generated: 11 Jun 2026 10:21:38 PM\n"
    "\n"
)

RECIPIENT_CSV = BANNER + (
    "Recipient,2020,2021,2022,2023,2024,2015-2025,Percentage,"
    "Sum total years,Percentage of total\n"
    "Ukraine,18,44,2967,4294,5341,15056,4.6%,15056,4.6%\n"
    "Myanmar,217,67,229,132,222,2097,0.6%,2097,0.6%\n"
    "Bahamas,0 ,,,,,0 ,0.0%,0 ,0.0%\n"
    "NATO**,465,240,240,,120,1313,0.4%,1313,0.4%\n"
    "Total world import,24055,27084,33297,29527,30721,324103,100%,324103,\n"
)

EXPORTER_CSV = BANNER + (
    "Exports by,2020,2021,2022,2023,2024,2015-2025,Percentage,"
    "Sum total years,Percentage of total\n"
    "Russia,3660,2397,2566,1513,1994,45536,14%,45536,14%\n"
)

WEAPON_CSV = BANNER + (
    ",2020,2021,2022,2023,2024,2015-2025,Percentage,"
    "Sum total years,Percentage of total\n"
    "Aircraft,11321,13936,14353,10104,12681,140271,43%,140271,43%\n"
)


def test_recipient_csv_parses_and_excludes_aggregates():
    df = parse_tiv_csv(RECIPIENT_CSV)
    assert set(df["status"]) == {"tiv_annual"}
    ukr = df[df["recipient"] == "Ukraine"]
    assert len(ukr) == 5
    assert ukr[ukr["delivery_year_last"] == 2024]["total_tiv"].iloc[0] == 5341
    # summary columns ('2015-2025', 'Percentage'...) must not become years
    assert df["delivery_year_last"].between(2020, 2024).all()
    # world-total footer dropped; NATO** kept (drops later at country match)
    assert not df["recipient"].str.lower().str.startswith("total").any()
    # '0 ' marker (<0.5 TIV) treated as zero and dropped
    assert "Bahamas" not in set(df["recipient"])


def test_exporter_csv_maps_to_supplier_role():
    df = parse_tiv_csv(EXPORTER_CSV)
    assert set(df["supplier"]) == {"Russia"}
    assert df["recipient"].isna().all()


def test_weapon_category_csv_rejected():
    with pytest.raises(ValueError, match="weapon-category"):
        parse_tiv_csv(WEAPON_CSV)


def test_recipient_csv_drives_velocity():
    df = parse_tiv_csv(RECIPIENT_CSV)
    df = df.rename(columns={"recipient": "recipient_country"})
    df["recipient_country"] = df["recipient_country"].map(
        {"Ukraine": "UKR", "Myanmar": "MMR"})
    vel = transfer_velocity(df[df["recipient_country"].notna()])
    ukr_2022 = vel[(vel.recipient_country == "UKR") & (vel.year == 2022)].iloc[0]
    assert ukr_2022["transfer_spike_flag"]  # 2967 vs avg(18, 44)
