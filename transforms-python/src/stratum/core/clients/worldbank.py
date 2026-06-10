"""World Bank clients — classic v2 API (default) + Data360 fallback.

The classic API (api.worldbank.org/v2) is keyless and still maintained;
Data360 (data360api.worldbank.org) is the World Bank's newer platform.
Both functions return identical row dicts, so the rest of the pipeline
doesn't care which one fed it. Data360 indicator IDs are derived from the
classic codes: NY.GDP.MKTP.CD -> WB_WDI_NY_GDP_MKTP_CD.
"""
from __future__ import annotations

import logging
from typing import Any

from stratum.core.http import get_json

log = logging.getLogger(__name__)

DATA360_PAGE_SIZE = 1000  # API hard cap per call; paginate with skip


def fetch_indicator(
    session: Any,
    base_url: str,
    indicator: str,
    *,
    start_year: int,
    end_year: int,
    per_page: int = 20000,
) -> list[dict]:
    """All countries, one indicator, year range. Handles API pagination."""
    rows: list[dict] = []
    page = 1
    while True:
        url = f"{base_url}/v2/country/all/indicator/{indicator}"
        data = get_json(session, url, params={
            "format": "json",
            "per_page": per_page,
            "date": f"{start_year}:{end_year}",
            "page": page,
        })
        if not isinstance(data, list) or len(data) < 2 or data[1] is None:
            break
        meta, records = data[0], data[1]
        for r in records:
            rows.append({
                "indicator_code": indicator,
                "country_iso3": r.get("countryiso3code") or (r.get("country") or {}).get("id"),
                "country_name": (r.get("country") or {}).get("value"),
                "year": int(r["date"]) if str(r.get("date", "")).isdigit() else None,
                "value": r.get("value"),
            })
        if page >= int(meta.get("pages", 1)):
            break
        page += 1
    log.info("worldbank: %s -> %d rows", indicator, len(rows))
    return rows


def fetch_indicator_data360(
    session: Any,
    base_url: str,
    indicator: str,
    *,
    start_year: int,
    end_year: int,
) -> list[dict]:
    """Same indicator via Data360. `indicator` is the CLASSIC code
    (e.g. NY.GDP.MKTP.CD); the WB_WDI Data360 ID is derived from it."""
    data360_id = "WB_WDI_" + indicator.replace(".", "_")
    rows: list[dict] = []
    skip = 0
    while True:
        data = get_json(session, f"{base_url}/data360/data", params={
            "DATABASE_ID": "WB_WDI",
            "INDICATOR": data360_id,
            "timePeriodFrom": start_year,
            "timePeriodTo": end_year,
            "skip": skip,
        })
        records = data.get("value", []) or []
        for r in records:
            year = str(r.get("TIME_PERIOD", ""))
            try:
                value = float(r["OBS_VALUE"]) if r.get("OBS_VALUE") is not None else None
            except (TypeError, ValueError):
                value = None
            rows.append({
                "indicator_code": indicator,
                "country_iso3": r.get("REF_AREA"),
                "country_name": None,
                "year": int(year) if year.isdigit() else None,
                "value": value,
            })
        total = int(data.get("count", 0))
        skip += DATA360_PAGE_SIZE
        if skip >= total or not records:
            break
    log.info("worldbank data360: %s -> %d rows", indicator, len(rows))
    return rows
