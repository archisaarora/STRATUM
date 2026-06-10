"""Synthetic raw-data scenario for pipeline validation and demos.

Generates plausible sample files for every raw dataset with a planted
storyline (all figures fictional):

  * IRN — propellant/ammonia imports triple in the latest year while the
    declared budget stays flat and diverges from the World Bank figure
    => material_anomaly + budget_discrepancy => COMPOUND SIGNAL
  * USA — hypersonics contract awards accelerate 4x year-over-year
    => procurement_acceleration
  * MMR — arms deliveries from RUS spike far above the rolling average
    => arms_transfer_spike
  * ETH — sustained high conflict intensity (GDELT + ACLED)
  * CHN — titanium imports grow ~5%/yr: must NOT fire (discrimination test)
  * One USASpending recipient matches an OpenSanctions entity

Used by scripts/make_sample_raw_data.py (writes uploadable files) and by
test/test_end_to_end.py (full pipeline integration test).
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

LATEST_YEAR = 2025
YEARS = list(range(2020, LATEST_YEAR + 1))

COUNTRIES = [
    # iso3, iso2, m49, name, region, nato, monitored, aliases
    ("IRN", "IR", 364, "Iran", "Middle East", False, True,
     "Iran (Islamic Republic of)|Iran, Islamic Rep."),
    ("CHN", "CN", 156, "China", "East Asia", False, True, ""),
    ("RUS", "RU", 643, "Russia", "Eastern Europe & Eurasia", False, True,
     "Russian Federation"),
    ("MMR", "MM", 104, "Myanmar", "Southeast Asia", False, True, "Burma"),
    ("ETH", "ET", 231, "Ethiopia", "Sub-Saharan Africa", False, True, ""),
    ("PAK", "PK", 586, "Pakistan", "South Asia", False, True, ""),
    ("USA", "US", 840, "United States", "North America", True, False,
     "USA|United States of America"),
    ("FRA", "FR", 250, "France", "Western Europe", True, False, ""),
    ("GBR", "GB", 826, "United Kingdom", "Western Europe", True, False, "UK"),
]


def reference_frame() -> pd.DataFrame:
    return pd.DataFrame(
        COUNTRIES,
        columns=["iso3", "iso2", "m49_code", "country_name", "region",
                 "is_nato", "is_monitored", "aliases"],
    )


# ----------------------------------------------------------------- SIPRI
MILEX_USD_M = {  # US$ millions, flat IRN is the point
    "Iran": [10_000, 10_200, 10_100, 10_300, 10_200, 10_400],
    "China": [240_000, 252_000, 265_000, 278_000, 292_000, 307_000],
    "Russia": [61_000, 63_000, 75_000, 94_000, 109_000, 120_000],
    "United States": [778_000, 800_000, 812_000, 860_000, 886_000, 905_000],
    "France": [52_000, 53_000, 53_500, 56_000, 61_000, 64_000],
    "Myanmar": [2_100, 2_000, 1_900, 1_950, 2_000, 2_050],
    "Ethiopia": [460, 500, 1_000, 1_100, 1_200, 1_300],
}
MILEX_PCT_GDP = {
    "Iran": [2.5, 2.4, 2.3, 2.2, 2.1, 2.1],
    "China": [1.7, 1.7, 1.6, 1.7, 1.7, 1.7],
    "Russia": [4.1, 4.1, 4.7, 5.9, 6.7, 7.1],
    "United States": [3.7, 3.5, 3.3, 3.4, 3.4, 3.4],
    "France": [2.0, 1.9, 1.9, 2.0, 2.1, 2.1],
    "Myanmar": [3.0, 2.9, 2.9, 3.0, 3.0, 3.0],
    "Ethiopia": [0.5, 0.5, 0.8, 0.8, 0.8, 0.8],
}


def sipri_milex_workbook() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    cur = wb.active
    cur.title = "Current US$"
    cur.append(["SIPRI Military Expenditure Database (SAMPLE DATA)"])
    cur.append([])
    cur.append(["Country", "Notes"] + YEARS)
    for country, vals in MILEX_USD_M.items():
        cur.append([country, ""] + vals)
    share = wb.create_sheet("Share of GDP")
    share.append(["Country", "Notes"] + YEARS)
    for country, vals in MILEX_PCT_GDP.items():
        share.append([country, ""] + vals)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def sipri_arms_csv() -> str:
    lines = [
        "SIPRI Arms Transfers Database (SAMPLE DATA)",
        "Supplier,Recipient,Year of order,Number ordered,Weapon designation,"
        "Weapon description,Number delivered,Year(s) of delivery,Status,"
        "SIPRI TIV per unit,SIPRI TIV for total order",
    ]
    baseline = [
        ("Russia", "Myanmar", 2019, 2, "Mi-35", "Combat helicopter", 2, "2020", "Delivered", 9, 18),
        ("China", "Myanmar", 2020, 1, "JF-17", "FGA aircraft", 1, "2021", "Delivered", 20, 20),
        ("Russia", "Myanmar", 2021, 1, "Su-30", "FGA aircraft", 1, "2022", "Delivered", 33, 33),
        ("China", "Myanmar", 2022, 2, "K-8", "Trainer aircraft", 2, "2023", "Delivered", 7, 14),
        ("Russia", "Myanmar", 2023, 1, "Mi-17", "Transport helicopter", 1, "2024", "Delivered", 12, 12),
        # 2025 spike: ~10x the rolling average
        ("Russia", "Myanmar", 2024, 6, "Su-30", "FGA aircraft", 6, "2025", "Delivered", 33, 198),
        ("China", "Pakistan", 2021, 4, "Type-054A/P", "Frigate", 2, "2022-2023", "Delivered", 52, 208),
        ("China", "Pakistan", 2022, 25, "VT-4", "Tank", 25, "2023", "Delivered", 4, 100),
        ("United States", "France", 2021, 3, "C-130J", "Transport aircraft", 3, "2022", "Delivered", 30, 90),
    ]
    for r in baseline:
        lines.append(",".join(str(x) for x in r))
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------- Comtrade
def comtrade_raw() -> pd.DataFrame:
    rows = []

    def series(iso3, m49, name, hs, desc, values):
        for year, value in zip(YEARS, values):
            rows.append({
                "reporter_iso3": iso3, "reporter_m49": m49,
                "reporter_desc": name, "partner_m49": 0,
                "partner_desc": "World", "hs_code": hs,
                "commodity_description": desc, "flow_code": "M",
                "trade_value_usd": float(value),
                "net_weight_kg": float(value) / 8.0,
                "year": year, "month": 52,
                "checkpoint_key": f"{iso3}:{year}",
            })

    rng = np.random.default_rng(7)

    def noisy(base, growth, spike_last=None):
        vals = [base * (1 + growth) ** i * rng.uniform(0.97, 1.03)
                for i in range(len(YEARS))]
        if spike_last:
            vals[-1] = vals[-2] * spike_last
        return vals

    # IRN propellant precursors triple in 2025 (compound-signal driver)
    series("IRN", 364, "Iran", "3601", "Propellant powders",
           noisy(95e6, 0.01, spike_last=3.3))
    series("IRN", 364, "Iran", "2814", "Ammonia", noisy(60e6, 0.02, spike_last=2.9))
    series("IRN", 364, "Iran", "8542", "Integrated circuits", noisy(40e6, 0.03))
    # CHN titanium grows gently — must not fire
    series("CHN", 156, "China", "8108", "Titanium and articles", noisy(800e6, 0.05))
    series("CHN", 156, "China", "8542", "Integrated circuits", noisy(35e9, 0.04))
    # Baseline cohort
    series("FRA", 250, "France", "3601", "Propellant powders", noisy(120e6, 0.01))
    series("FRA", 250, "France", "8108", "Titanium and articles", noisy(300e6, 0.02))
    series("USA", 840, "United States", "8108", "Titanium and articles",
           noisy(1.2e9, 0.02))
    series("MMR", 104, "Myanmar", "2710", "Petroleum oils", noisy(900e6, 0.0))
    return pd.DataFrame(rows)


# ------------------------------------------------------------ World Bank
GDP_USD_B = {
    "IRN": 400, "CHN": 18_500, "RUS": 2_000, "MMR": 65,
    "ETH": 160, "PAK": 380, "USA": 28_000, "FRA": 3_100, "GBR": 3_400,
}
WB_MILEX_PCT = {  # IRN World Bank figure implies ~16B vs ~10B declared
    "IRN": 4.0, "CHN": 1.7, "RUS": 6.5, "MMR": 3.1,
    "ETH": 0.8, "PAK": 2.8, "USA": 3.4, "FRA": 2.0, "GBR": 2.3,
}


def worldbank_raw() -> pd.DataFrame:
    rows = []
    for iso3, gdp_b in GDP_USD_B.items():
        name = dict((c[0], c[3]) for c in COUNTRIES)[iso3]
        for year in YEARS:
            gdp = gdp_b * 1e9 * (1.02 ** (year - YEARS[0]))
            for code, value in [
                ("NY.GDP.MKTP.CD", gdp),
                ("MS.MIL.XPND.GD.ZS", WB_MILEX_PCT[iso3]),
                ("SP.POP.TOTL", 5e7),
                ("NY.GDP.MKTP.KD.ZG", 2.5),
            ]:
                rows.append({"indicator_code": code, "country_iso3": iso3,
                             "country_name": name, "year": year, "value": value})
    return pd.DataFrame(rows)


# ----------------------------------------------------------- USASpending
HYPERSONIC_DESCRIPTIONS = [
    "Hypersonic glide vehicle thermal protection system development and "
    "flight test instrumentation",
    "Scramjet propulsion test article fabrication and ground demonstration "
    "for high-speed strike weapon prototype",
    "Boost-glide hypersonic weapon system integration engineering and "
    "manufacturing development",
    "Mach 5+ aeroshell materials qualification testing and prototype "
    "demonstration support",
]
OTHER_DESCRIPTIONS = [
    ("Cybersecurity operations support including zero trust architecture "
     "implementation and security operations center staffing", "541512"),
    ("Biosurveillance and medical countermeasure research for biological "
     "threat agents", "541714"),
    ("Janitorial and grounds maintenance services for installation buildings",
     "561720"),
    ("Unmanned aircraft system counter-UAS radar integration and electronic "
     "warfare countermeasures development", "334511"),
]


def usaspending_raw() -> pd.DataFrame:
    rows = []
    idx = 0

    def add(date, desc, naics, value, recipient="Lockheed Martin Corp."):
        nonlocal idx
        idx += 1
        rows.append({
            "award_id": f"CONT_AWD_{idx:04d}",
            "display_award_id": f"W9113M-{idx:04d}",
            "recipient_name": recipient,
            "recipient_country_code": "USA",
            "awarding_agency_name": "Department of Defense",
            "awarding_sub_agency": "Department of the Army",
            "funding_agency_name": "Department of Defense",
            "award_description": desc,
            "total_obligated_amount": value,
            "period_of_performance_start_date": date,
            "period_of_performance_current_end_date": "2027-12-31",
            "naics_code": naics,
            "product_or_service_code": "AC13",
            "pop_country_code": "USA",
            "ingest_window_start": date[:8] + "01",
            "ingest_window_end": date[:8] + "28",
        })

    # Prior 12m window (2024-06..2025-05): 2 hypersonics awards
    add("2024-08-15", HYPERSONIC_DESCRIPTIONS[0], "336414", 12e6)
    add("2025-02-10", HYPERSONIC_DESCRIPTIONS[1], "336414", 15e6,
        "Raytheon Co.")
    # Current 12m window (2025-06..2026-05): 8 awards, much larger values
    dates = ["2025-06-20", "2025-08-05", "2025-09-18", "2025-11-02",
             "2025-12-15", "2026-02-01", "2026-03-22", "2026-05-10"]
    for i, d in enumerate(dates):
        add(d, HYPERSONIC_DESCRIPTIONS[i % 4], "336414", 45e6 + i * 5e6,
            ["Lockheed Martin Corp.", "Raytheon Co.",
             "Northrop Grumman Corp."][i % 3])
    # Background contracts incl. one sanctioned-entity match
    for i, (desc, naics) in enumerate(OTHER_DESCRIPTIONS):
        add(f"2025-0{i + 3}-12", desc, naics, 3e6, "Leidos Inc.")
    add("2025-07-30", "Air charter and heavy cargo transportation services "
        "for contingency logistics", "481212", 8e6, "Aviacon Zitotrans JSC")
    return pd.DataFrame(rows)


def dod_contracts_raw() -> pd.DataFrame:
    rows = [
        {
            "contract_id": "dod_sample_0001",
            "announcement_date_text": "May 28, 2026",
            "contractor_name": "General Dynamics Electric Boat Corp.",
            "contract_value_usd": 517_255_000.0,
            "description_text": (
                "General Dynamics Electric Boat Corp., Groton, Connecticut, is "
                "awarded a $517,255,000 modification for Virginia-class "
                "submarine lead yard support, undersea warfare systems "
                "engineering and towed array sonar integration. Naval Sea "
                "Systems Command is the contracting activity."),
            "contracting_command": "Navy",
            "contracting_activity": "Naval Sea Systems Command",
            "source_url": "https://www.defense.gov/News/Contracts/sample/1",
        },
        {
            "contract_id": "dod_sample_0002",
            "announcement_date_text": "June 2, 2026",
            "contractor_name": "Raytheon Co.",
            "contract_value_usd": 96_000_000.0,
            "description_text": (
                "Raytheon Co., Tucson, Arizona, has been awarded a $96,000,000 "
                "contract for production of hypersonic attack cruise missile "
                "test articles and scramjet propulsion hardware. The Air Force "
                "Life Cycle Management Center is the contracting activity."),
            "contracting_command": "Air Force",
            "contracting_activity": "Air Force Life Cycle Management Center",
            "source_url": "https://www.defense.gov/News/Contracts/sample/2",
        },
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------- OpenSanctions
def opensanctions_csv() -> str:
    return (
        "id,schema,name,aliases,birth_date,countries,addresses,identifiers,"
        "sanctions,phones,emails,dataset,first_seen,last_seen\n"
        "NK-1,Company,Rosoboronexport JSC,ROE,,ru,,,OFAC SDN,,,us_ofac_sdn,"
        "2022-04-01,2026-05-01\n"
        "NK-2,Company,Aviacon Zitotrans JSC,Aviacon Zitotrans,,ru,,,"
        "OFAC SDN,,,us_ofac_sdn,2022-04-01,2026-05-01\n"
        "NK-3,Person,Sample Person,,1960-01-01,ir,,,EU FSF,,,eu_fsf,"
        "2021-01-01,2026-05-01\n"
        "NK-4,Company,Mahan Air,Mahan Airlines,,ir,,,OFAC SDN,,,us_ofac_sdn,"
        "2019-01-01,2026-05-01\n"
    )


# ----------------------------------------------------------- GDELT/ACLED
def gdelt_raw() -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(11)
    dates = pd.date_range("2025-01-01", "2026-05-31", freq="D")
    profiles = {
        "ETH": (40, 12, -7.2), "MMR": (25, 8, -6.5), "IRN": (15, 5, -4.0),
        "FRA": (3, 1, 1.5), "USA": (6, 2, 0.5), "CHN": (8, 2, -1.0),
    }
    for d in dates:
        for iso3, (mean_ev, sd, goldstein) in profiles.items():
            n = max(0, int(rng.normal(mean_ev, sd)))
            if n == 0:
                continue
            rows.append({
                "event_date_int": int(d.strftime("%Y%m%d")),
                "actor1_country": iso3,
                "event_root_code": str(rng.choice(["14", "17", "18", "19"])),
                "event_count": n,
                "avg_goldstein": goldstein + rng.normal(0, 0.5),
                "total_mentions": n * 12,
                "total_sources": n * 3,
            })
    return pd.DataFrame(rows)


def acled_raw() -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(13)
    dates = pd.date_range("2025-01-01", "2026-05-31", freq="3D")
    for i, d in enumerate(dates):
        rows.append({
            "event_id_cnty": f"ETH{i:05d}", "event_date": d.date().isoformat(),
            "year": d.year, "event_type": "Battles",
            "sub_event_type": "Armed clash", "country": "Ethiopia",
            "admin1": "Amhara", "location": "Sample",
            "latitude": 11.6 + rng.normal(0, 0.5),
            "longitude": 37.4 + rng.normal(0, 0.5),
            "actor1": "Military Forces of Ethiopia", "actor2": "Militia",
            "fatalities": int(max(0, rng.normal(9, 5))),
            "notes": "sample event", "source": "sample",
        })
        if i % 4 == 0:
            rows.append({
                "event_id_cnty": f"MMR{i:05d}", "event_date": d.date().isoformat(),
                "year": d.year, "event_type": "Battles",
                "sub_event_type": "Armed clash", "country": "Myanmar",
                "admin1": "Sagaing", "location": "Sample",
                "latitude": 22.0, "longitude": 95.0,
                "actor1": "Military Forces of Myanmar", "actor2": "PDF",
                "fatalities": int(max(0, rng.normal(6, 3))),
                "notes": "sample event", "source": "sample",
            })
    return pd.DataFrame(rows)
