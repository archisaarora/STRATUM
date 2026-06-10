import pandas as pd

from stratum.core.countries import CountryIndex


def make_index() -> CountryIndex:
    ref = pd.DataFrame([
        {"iso3": "RUS", "iso2": "RU", "m49_code": 643, "country_name": "Russia",
         "region": "Eastern Europe & Eurasia", "is_nato": False, "is_monitored": True,
         "aliases": "Russian Federation|USSR|Soviet Union"},
        {"iso3": "PRK", "iso2": "KP", "m49_code": 408, "country_name": "North Korea",
         "region": "East Asia", "is_nato": False, "is_monitored": True,
         "aliases": "Korea, North|Korea, Dem. People's Rep.|DPRK"},
        {"iso3": "USA", "iso2": "US", "m49_code": 840, "country_name": "United States",
         "region": "North America", "is_nato": True, "is_monitored": False,
         "aliases": "USA|United States of America|U.S."},
        {"iso3": "CIV", "iso2": "CI", "m49_code": 384, "country_name": "Côte d'Ivoire",
         "region": "", "is_nato": False, "is_monitored": False,
         "aliases": "Cote d'Ivoire|Ivory Coast"},
    ])
    return CountryIndex.from_reference(ref)


def test_resolves_names_aliases_codes():
    idx = make_index()
    assert idx.to_iso3("Russian Federation") == "RUS"
    assert idx.to_iso3("russia") == "RUS"
    assert idx.to_iso3("USSR") == "RUS"
    assert idx.to_iso3("Korea, Dem. People's Rep.") == "PRK"
    assert idx.to_iso3("US") == "USA"          # ISO2
    assert idx.to_iso3("840") == "USA"         # M49 as string
    assert idx.to_iso3(643) == "RUS"           # M49 as int
    assert idx.to_iso3("RUS") == "RUS"         # ISO3 passthrough
    assert idx.to_iso3("Côte d’Ivoire") == "CIV"  # accents + smart quote
    assert idx.to_iso3("Atlantis") is None
    assert idx.to_iso3(None) is None


def test_standardize_column_reports_unmatched():
    idx = make_index()
    df = pd.DataFrame({"country": ["Russia", "Narnia", "United States of America"]})
    out, unmatched = idx.standardize_column(df, "country", "iso3")
    assert out["iso3"].iloc[0] == "RUS"
    assert pd.isna(out["iso3"].iloc[1])
    assert out["iso3"].iloc[2] == "USA"
    assert unmatched["country"].tolist() == ["Narnia"]


def test_monitored_and_meta():
    idx = make_index()
    assert idx.monitored() == ["PRK", "RUS"]
    assert idx.name_of("PRK") == "North Korea"
    assert idx.region_of("RUS") == "Eastern Europe & Eurasia"
