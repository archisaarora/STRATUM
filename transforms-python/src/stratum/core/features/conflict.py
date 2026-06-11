"""Transform 2.6 core — monthly conflict-intensity score per country.

Blends GDELT (event tempo + Goldstein severity) with ACLED (fatalities)
into a 0–1 score using global cross-sectional percentiles per month, so a
score of 0.9 means "in the 90th percentile of world conflict activity that
month" — comparable across countries and over time.

    intensity = 0.4 * gdelt_event_pctile
              + 0.3 * goldstein_severity_pctile
              + 0.3 * acled_fatality_pctile
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def monthly_intensity(
    gdelt_daily: pd.DataFrame | None,   # country_code, date, conflict_event_count, avg_goldstein
    acled_events: pd.DataFrame | None,  # country_code, event_date, fatalities
) -> pd.DataFrame:
    frames = []

    if gdelt_daily is not None and len(gdelt_daily):
        g = gdelt_daily.copy()
        g["month"] = pd.to_datetime(g["date"]).dt.to_period("M").dt.to_timestamp()
        gm = (
            g.groupby(["country_code", "month"])
            .agg(
                gdelt_events=("conflict_event_count", "sum"),
                avg_goldstein=("avg_goldstein", "mean"),
            )
            .reset_index()
        )
        frames.append(gm)

    if acled_events is not None and len(acled_events):
        a = acled_events.copy()
        a["month"] = pd.to_datetime(a["event_date"]).dt.to_period("M").dt.to_timestamp()
        am = (
            a.groupby(["country_code", "month"])
            .agg(acled_events=("event_date", "count"), acled_fatalities=("fatalities", "sum"))
            .reset_index()
        )
        frames.append(am)

    if not frames:
        return pd.DataFrame(columns=[
            "country_code", "month", "intensity_score", "trend_12m",
            "gdelt_events", "avg_goldstein", "acled_events", "acled_fatalities",
        ])

    df = frames[0]
    for other in frames[1:]:
        df = df.merge(other, on=["country_code", "month"], how="outer")
    for col in ("gdelt_events", "avg_goldstein", "acled_events", "acled_fatalities"):
        if col not in df:
            df[col] = np.nan
        # numeric coercion before fillna avoids object-dtype downcasting
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["gdelt_events"] = df["gdelt_events"].fillna(0.0)
    df["acled_fatalities"] = df["acled_fatalities"].fillna(0.0)
    # Goldstein: -10 (most conflictual) .. +10 — invert into a severity scale.
    df["goldstein_severity"] = (10.0 - df["avg_goldstein"].fillna(10.0)) / 20.0

    by_month = df.groupby("month")
    df["event_pctile"] = by_month["gdelt_events"].rank(pct=True)
    df["severity_pctile"] = by_month["goldstein_severity"].rank(pct=True)
    df["fatality_pctile"] = by_month["acled_fatalities"].rank(pct=True)

    df["intensity_score"] = (
        0.4 * df["event_pctile"]
        + 0.3 * df["severity_pctile"]
        + 0.3 * df["fatality_pctile"]
    ).round(4)

    df = df.sort_values(["country_code", "month"])
    df["trend_12m"] = (
        df.groupby("country_code")["intensity_score"]
        .transform(lambda s: s - s.shift(12))
        .round(4)
    )
    return df
