import io

import openpyxl
import pandas as pd

from stratum.core.parsing.opensanctions import build_org_name_index, parse_targets
from stratum.core.parsing.sipri_arms import parse_trade_register
from stratum.core.parsing.sipri_milex import parse_workbook
from stratum.core.text import normalize_company, parse_money, stable_id


def test_normalize_company():
    assert normalize_company("Lockheed Martin Corp.") == "lockheed martin"
    assert normalize_company("RAYTHEON COMPANY") == "raytheon"
    assert normalize_company("BAE Systems plc") == "bae systems"
    assert normalize_company(None) == ""


def test_parse_money():
    assert parse_money("awarded a $13,387,408 contract") == 13_387_408
    assert parse_money("a $1.2 billion deal") == 1.2e9
    assert parse_money("$45 million ceiling") == 45e6
    assert parse_money("no dollars here") is None


def test_stable_id_deterministic():
    assert stable_id("a", 1, prefix="x_") == stable_id("a", 1, prefix="x_")
    assert stable_id("a", 1) != stable_id("a", 2)


def _sipri_milex_workbook() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Current US$"
    ws.append(["Military expenditure by country", None, None, None])
    ws.append([None, None, None, None])
    ws.append(["Country", "Notes", 2021, 2022])
    ws.append(["Russia", "", 65900.5, "..."])
    ws.append(["North Korea", "", "xxx", "xxx"])
    ws.append(["USA", "", 800672.0, 876943.0])
    ws2 = wb.create_sheet("Share of GDP")
    ws2.append(["Country", "Notes", 2021, 2022])
    ws2.append(["Russia", "", 3.6, 4.1])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_sipri_milex_workbook():
    df = parse_workbook(_sipri_milex_workbook())
    rus = df[(df.country_name_raw == "Russia")
             & (df.measure == "expenditure_current_usd")]
    assert len(rus) == 1  # 2022 '...' dropped
    assert rus.iloc[0]["value"] == 65900.5 * 1e6  # millions -> USD
    share = df[df.measure == "expenditure_pct_gdp"]
    assert share.iloc[0]["value"] == 3.6  # no scaling for %GDP
    assert "North Korea" not in set(
        df[df.measure == "expenditure_current_usd"]["country_name_raw"])


SIPRI_ARMS_CSV = """Arms transfers database
Generated: 01 June 2026
Supplier,Recipient,Year of order,Number ordered,Weapon designation,Weapon description,Number delivered,Year(s) of delivery,Status,SIPRI TIV per unit,SIPRI TIV for total order
Russia,Myanmar,2021,6,Su-30,FGA aircraft,6,2022-2024,Delivered,(0.5),3.0
China,Pakistan,2022,4,Type-054A,Frigate,2,2023,Partially delivered,52,208
"""


def test_parse_sipri_arms_register():
    df = parse_trade_register(SIPRI_ARMS_CSV.encode())
    assert len(df) == 2
    row = df.iloc[0]
    assert row["supplier"] == "Russia"
    assert row["tiv_per_unit"] == 0.5       # parentheses handled
    assert row["total_tiv"] == 3.0
    assert row["delivery_year_last"] == 2024  # range -> last year
    assert df["transfer_id"].is_unique


OPENSANCTIONS_CSV = """id,schema,name,aliases,birth_date,countries,addresses,identifiers,sanctions,phones,emails,dataset,first_seen,last_seen
Q1,Company,Rosoboronexport JSC,ROE;Rosoboron Export,,ru,,,OFAC SDN,,,us_ofac_sdn,2022-01-01,2026-01-01
Q2,Person,John Doe,,1970-01-01,us,,,EU list,,,eu_fsf,2023-01-01,2026-01-01
Q3,LegalEntity,Mahan Air,,,ir,,,OFAC SDN,,,us_ofac_sdn,2020-01-01,2026-01-01
"""


def test_parse_opensanctions_and_org_index():
    df = parse_targets(OPENSANCTIONS_CSV)
    assert len(df) == 3
    assert df["is_organization"].sum() == 2
    names = build_org_name_index(df)
    assert "rosoboronexport" in names
    assert "mahan air" in names
    assert "john doe" not in names  # persons excluded
