"""World Bank Open Data client — free, keyless REST API."""
from __future__ import annotations

import logging
from typing import Any

from stratum.core.http import get_json

log = logging.getLogger(__name__)


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
