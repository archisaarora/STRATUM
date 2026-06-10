"""Generate reference-data/ref_country_iso_lookup.csv.

Dev-time script (requires `pycountry`). The generated CSV is committed and
uploaded to Foundry as the `ref_country_iso_lookup` dataset — no runtime
pycountry dependency anywhere in the pipeline. Per the STRATUM quality
requirements, ALL country-name standardization goes through this table.

Columns:
    iso3, iso2, m49_code, country_name, region, is_nato, is_monitored, aliases
    (aliases is a pipe-separated list of name variants seen in SIPRI,
    World Bank, UN Comtrade, ACLED, GDELT and USASpending exports)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pycountry

OUT = Path(__file__).resolve().parents[1] / "reference-data" / "ref_country_iso_lookup.csv"

# Countries on the STRATUM monitored list (build prompt, Transform 1.5).
MONITORED = {
    "CHN", "RUS", "IRN", "PRK", "BLR", "MMR", "VEN", "SYR", "YEM",
    "ETH", "SDN", "PAK", "IND",
}

# NATO members (32, post-2024 incl. Finland and Sweden) — baseline cohort.
NATO = {
    "ALB", "BEL", "BGR", "CAN", "HRV", "CZE", "DNK", "EST", "FIN", "FRA",
    "DEU", "GRC", "HUN", "ISL", "ITA", "LVA", "LTU", "LUX", "MNE", "NLD",
    "MKD", "NOR", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "TUR",
    "GBR", "USA",
}

# Name variants observed across the source systems, keyed by ISO3.
ALIASES: dict[str, list[str]] = {
    "AFG": ["Afghanistan, Islamic Rep. of"],
    "BHS": ["The Bahamas", "Bahamas, The"],
    "BOL": ["Bolivia (Plurinational State of)", "Bolivia"],
    "BIH": ["Bosnia-Herzegovina", "Bosnia & Herzegovina"],
    "BRN": ["Brunei", "Brunei Darussalam"],
    "CPV": ["Cape Verde", "Cabo Verde"],
    "CIV": ["Cote d'Ivoire", "Côte d'Ivoire", "Cote dIvoire", "Ivory Coast"],
    "COD": [
        "Congo, Dem. Rep.", "DR Congo", "DRC", "Congo, DR",
        "Democratic Republic of the Congo", "Congo, the Democratic Republic of the",
        "Congo (Kinshasa)", "Zaire",
    ],
    "COG": ["Congo, Rep.", "Congo, Republic", "Congo-Brazzaville", "Congo (Brazzaville)", "Republic of the Congo", "Congo"],
    "CZE": ["Czech Republic", "Czechia", "Czechoslovakia"],
    "DEU": ["Germany", "German Democratic Republic", "German DR", "West Germany", "Germany (FRG)"],
    "EGY": ["Egypt, Arab Rep.", "Egypt"],
    "GMB": ["The Gambia", "Gambia, The"],
    "HKG": ["Hong Kong", "China, Hong Kong SAR", "Hong Kong SAR, China"],
    "IRN": ["Iran", "Iran (Islamic Republic of)", "Iran, Islamic Rep.", "Iran, Islamic Republic of"],
    "KGZ": ["Kyrgyzstan", "Kyrgyz Republic"],
    "PRK": [
        "North Korea", "Korea, North", "Korea, Dem. People's Rep.",
        "Democratic People's Republic of Korea", "Dem. People's Rep. of Korea",
        "Korea, Dem. People's Rep. of", "DPRK", "Korea North",
    ],
    "KOR": [
        "South Korea", "Korea, South", "Korea, Rep.", "Republic of Korea",
        "Rep. of Korea", "Korea South", "Korea, Republic of",
    ],
    "LAO": ["Laos", "Lao PDR", "Lao People's Democratic Republic", "Lao People's Dem. Rep."],
    "MAC": ["Macao", "Macau", "China, Macao SAR", "Macao SAR, China"],
    "MDA": ["Moldova", "Republic of Moldova", "Moldova, Rep. of"],
    "MMR": ["Myanmar", "Burma", "Myanmar (Burma)"],
    "MKD": ["North Macedonia", "Macedonia", "Macedonia, FYR", "FYR Macedonia"],
    "NLD": ["Netherlands", "Netherlands (Kingdom of the)", "The Netherlands", "Holland"],
    "PSE": ["Palestine", "State of Palestine", "West Bank and Gaza", "Palestinian Territories"],
    "RUS": ["Russia", "Russian Federation", "USSR", "Soviet Union"],
    "SVK": ["Slovakia", "Slovak Republic"],
    "SRB": ["Serbia", "Yugoslavia", "Serbia and Montenegro"],
    "KNA": ["St. Kitts and Nevis", "Saint Kitts and Nevis"],
    "LCA": ["St. Lucia", "Saint Lucia"],
    "VCT": ["St. Vincent and the Grenadines", "Saint Vincent and the Grenadines"],
    "SYR": ["Syria", "Syrian Arab Republic"],
    "TWN": ["Taiwan", "Taiwan, Province of China", "Chinese Taipei", "Other Asia, nes", "Taiwan (POC)"],
    "TZA": ["Tanzania", "United Republic of Tanzania", "Tanzania, United Rep. of"],
    "TUR": ["Turkey", "Türkiye", "Turkiye"],
    "ARE": ["UAE", "United Arab Emirates"],
    "GBR": ["UK", "United Kingdom", "United Kingdom of Great Britain and Northern Ireland", "Great Britain"],
    "USA": ["USA", "United States", "United States of America", "US", "U.S.", "United States Of America"],
    "VEN": ["Venezuela", "Venezuela, RB", "Venezuela (Bolivarian Republic of)", "Venezuela (Bolivarian Rep. of)"],
    "VNM": ["Vietnam", "Viet Nam", "Viet Nam, Socialist Republic of"],
    "YEM": ["Yemen", "Yemen, Rep.", "North Yemen", "Yemen, North", "South Yemen",
            "Yemen, South", "Yemen Arab Republic"],
    "SWZ": ["Eswatini", "Swaziland"],
    "TLS": ["Timor-Leste", "East Timor"],
    "FSM": ["Micronesia", "Micronesia, Fed. Sts.", "Micronesia (Federated States of)"],
    "STP": ["Sao Tome and Principe", "São Tomé and Príncipe"],
    "BLR": ["Belarus", "Belorussia", "Byelorussia"],
    "KHM": ["Cambodia", "Kampuchea"],
    "LKA": ["Sri Lanka", "Ceylon"],
    "ZWE": ["Zimbabwe", "Rhodesia"],
    "BFA": ["Burkina Faso", "Upper Volta"],
    "MHL": ["Marshall Islands", "Marshall Is."],
    "SLB": ["Solomon Islands", "Solomon Is."],
    "CAF": ["Central African Republic", "Central African Rep."],
    "DOM": ["Dominican Republic", "Dominican Rep."],
    "GNQ": ["Equatorial Guinea", "Eq. Guinea"],
    "TTO": ["Trinidad and Tobago", "Trinidad & Tobago"],
}

# UN-style region labels for the countries STRATUM actively reasons about.
REGIONS: dict[str, str] = {
    # Monitored
    "CHN": "East Asia", "RUS": "Eastern Europe & Eurasia", "IRN": "Middle East",
    "PRK": "East Asia", "BLR": "Eastern Europe & Eurasia", "MMR": "Southeast Asia",
    "VEN": "South America", "SYR": "Middle East", "YEM": "Middle East",
    "ETH": "Sub-Saharan Africa", "SDN": "Sub-Saharan Africa", "PAK": "South Asia",
    "IND": "South Asia",
    # NATO
    "ALB": "Southern Europe", "BEL": "Western Europe", "BGR": "Eastern Europe & Eurasia",
    "CAN": "North America", "HRV": "Southern Europe", "CZE": "Central Europe",
    "DNK": "Northern Europe", "EST": "Northern Europe", "FIN": "Northern Europe",
    "FRA": "Western Europe", "DEU": "Western Europe", "GRC": "Southern Europe",
    "HUN": "Central Europe", "ISL": "Northern Europe", "ITA": "Southern Europe",
    "LVA": "Northern Europe", "LTU": "Northern Europe", "LUX": "Western Europe",
    "MNE": "Southern Europe", "NLD": "Western Europe", "MKD": "Southern Europe",
    "NOR": "Northern Europe", "POL": "Central Europe", "PRT": "Southern Europe",
    "ROU": "Eastern Europe & Eurasia", "SVK": "Central Europe", "SVN": "Central Europe",
    "ESP": "Southern Europe", "SWE": "Northern Europe", "TUR": "Middle East",
    "GBR": "Western Europe", "USA": "North America",
    # Major suppliers / partners / neighbours that show up in flows
    "AUS": "Oceania", "JPN": "East Asia", "KOR": "East Asia", "TWN": "East Asia",
    "ISR": "Middle East", "SAU": "Middle East", "ARE": "Middle East",
    "QAT": "Middle East", "KWT": "Middle East", "OMN": "Middle East",
    "IRQ": "Middle East", "JOR": "Middle East", "LBN": "Middle East",
    "EGY": "North Africa", "DZA": "North Africa", "MAR": "North Africa",
    "LBY": "North Africa", "TUN": "North Africa",
    "UKR": "Eastern Europe & Eurasia", "GEO": "Eastern Europe & Eurasia",
    "ARM": "Eastern Europe & Eurasia", "AZE": "Eastern Europe & Eurasia",
    "KAZ": "Central Asia", "UZB": "Central Asia", "TKM": "Central Asia",
    "TJK": "Central Asia", "KGZ": "Central Asia", "MNG": "East Asia",
    "AFG": "South Asia", "BGD": "South Asia", "LKA": "South Asia", "NPL": "South Asia",
    "VNM": "Southeast Asia", "THA": "Southeast Asia", "IDN": "Southeast Asia",
    "MYS": "Southeast Asia", "SGP": "Southeast Asia", "PHL": "Southeast Asia",
    "KHM": "Southeast Asia", "LAO": "Southeast Asia", "BRN": "Southeast Asia",
    "BRA": "South America", "ARG": "South America", "CHL": "South America",
    "COL": "South America", "PER": "South America", "BOL": "South America",
    "ECU": "South America", "GUY": "South America", "SUR": "South America",
    "PRY": "South America", "URY": "South America",
    "MEX": "North America", "CUB": "Caribbean", "NIC": "Central America",
    "ZAF": "Sub-Saharan Africa", "NGA": "Sub-Saharan Africa", "KEN": "Sub-Saharan Africa",
    "ERI": "Sub-Saharan Africa", "SSD": "Sub-Saharan Africa", "SOM": "Sub-Saharan Africa",
    "TCD": "Sub-Saharan Africa", "MLI": "Sub-Saharan Africa", "NER": "Sub-Saharan Africa",
    "AGO": "Sub-Saharan Africa", "MOZ": "Sub-Saharan Africa", "COD": "Sub-Saharan Africa",
    "CHE": "Western Europe", "AUT": "Western Europe", "IRL": "Northern Europe",
    "SRB": "Southern Europe", "BIH": "Southern Europe", "MDA": "Eastern Europe & Eurasia",
    "CYP": "Southern Europe", "MLT": "Southern Europe", "NZL": "Oceania",
}


def main() -> None:
    rows = []
    for c in pycountry.countries:
        iso3 = c.alpha_3
        names = {c.name}
        if getattr(c, "official_name", None):
            names.add(c.official_name)
        if getattr(c, "common_name", None):
            names.add(c.common_name)
        names.update(ALIASES.get(iso3, []))
        # The primary display name: prefer the common/short variant.
        display = getattr(c, "common_name", None) or c.name
        aliases = sorted(n for n in names if n != display)
        rows.append({
            "iso3": iso3,
            "iso2": c.alpha_2,
            "m49_code": int(c.numeric),
            "country_name": display,
            "region": REGIONS.get(iso3, ""),
            "is_nato": iso3 in NATO,
            "is_monitored": iso3 in MONITORED,
            "aliases": "|".join(aliases),
        })
    # Kosovo: not ISO-assigned; SIPRI/ACLED/World Bank track it. m49_code 0
    # means "no UN M49 code" (CountryIndex skips 0 in the numeric lookup).
    rows.append({
        "iso3": "XKX", "iso2": "XK", "m49_code": 0, "country_name": "Kosovo",
        "region": "Southern Europe", "is_nato": False, "is_monitored": False,
        "aliases": "Republic of Kosovo",
    })
    rows.sort(key=lambda r: r["iso3"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} countries -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
