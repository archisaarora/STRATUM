"""Transform 2.4 core — budget credibility features.

Compares SIPRI declared military expenditure against the World Bank's
independently compiled figure (milex %GDP x GDP => implied USD), plus
year-over-year change and 5-year CAGR of declared spend.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def budget_discrepancy(
    sipri_milex: pd.DataFrame,       # country_code, year, measure, value (long)
    worldbank: pd.DataFrame,         # country_code, year, indicator_code, value
    *,
    flag_pct: float = 15.0,
) -> pd.DataFrame:
    sipri = (
        sipri_milex[sipri_milex["measure"] == "expenditure_current_usd"]
        .rename(columns={"value": "sipri_milex_usd"})
        [["country_code", "year", "sipri_milex_usd"]]
    )
    sipri_gdp_share = (
        sipri_milex[sipri_milex["measure"] == "expenditure_pct_gdp"]
        .rename(columns={"value": "sipri_milex_pct_gdp"})
        [["country_code", "year", "sipri_milex_pct_gdp"]]
    )

    wb = worldbank.pivot_table(
        index=["country_code", "year"], columns="indicator_code",
        values="value", aggfunc="first",
    ).reset_index()
    wb = wb.rename(columns={
        "NY.GDP.MKTP.CD": "gdp_usd",
        "MS.MIL.XPND.GD.ZS": "wb_milex_pct_gdp",
        "SP.POP.TOTL": "population",
        "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
    })
    for col in ("gdp_usd", "wb_milex_pct_gdp", "population", "gdp_growth_pct"):
        if col not in wb:
            wb[col] = np.nan

    df = sipri.merge(sipri_gdp_share, on=["country_code", "year"], how="left")
    df = df.merge(
        wb[["country_code", "year", "gdp_usd", "wb_milex_pct_gdp",
            "population", "gdp_growth_pct"]],
        on=["country_code", "year"], how="left",
    )
    df["wb_milex_usd_implied"] = df["gdp_usd"] * df["wb_milex_pct_gdp"] / 100.0
    df["sipri_wb_discrepancy_pct"] = np.where(
        df["wb_milex_usd_implied"] > 0,
        (df["sipri_milex_usd"] - df["wb_milex_usd_implied"]).abs()
        / df["wb_milex_usd_implied"] * 100.0,
        np.nan,
    )

    df = df.sort_values(["country_code", "year"])
    by_country = df.groupby("country_code")["sipri_milex_usd"]
    prev = by_country.shift(1)
    df["declared_yoy_change_pct"] = np.where(
        prev > 0, (df["sipri_milex_usd"] - prev) / prev * 100.0, np.nan
    )
    past5 = by_country.shift(5)
    df["declared_cagr_5y_pct"] = np.where(
        (past5 > 0) & (df["sipri_milex_usd"] > 0),
        ((df["sipri_milex_usd"] / past5) ** (1 / 5) - 1) * 100.0,
        np.nan,
    )
    df["budget_credibility_flag"] = df["sipri_wb_discrepancy_pct"] > flag_pct
    return df
