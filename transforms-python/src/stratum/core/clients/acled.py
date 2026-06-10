"""ACLED client. Supports both auth schemes:

- legacy: api.acleddata.com/acled/read?key=...&email=...
- 2025+ OAuth portal: bearer token against acleddata.com/api/acled/read

Register at acleddata.com (free for academic use) and store whichever
credential you were issued; the transform passes the right kwargs.
"""
from __future__ import annotations

import logging
from typing import Any

from stratum.core.http import get_json

log = logging.getLogger(__name__)

LEGACY_READ = "/acled/read"
PORTAL_READ = "/api/acled/read"
PAGE_SIZE = 5000

FIELDS = ("event_id_cnty|event_date|year|event_type|sub_event_type|country|iso|"
          "admin1|location|latitude|longitude|actor1|actor2|fatalities|notes|source")


def fetch_events(
    session: Any,
    base_url: str,
    *,
    start_date: str,
    end_date: str,
    api_key: str | None = None,
    email: str | None = None,
    bearer_token: str | None = None,
    countries: list[str] | None = None,
    max_pages: int = 200,
) -> list[dict]:
    """Pull events in [start_date, end_date]; paginates PAGE_SIZE at a time."""
    headers = {}
    params: dict[str, Any] = {
        "event_date": f"{start_date}|{end_date}",
        "event_date_where": "BETWEEN",
        "fields": FIELDS,
        "limit": PAGE_SIZE,
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
        path = PORTAL_READ
    else:
        params["key"] = api_key
        params["email"] = email
        path = LEGACY_READ
    if countries:
        params["country"] = "|".join(countries)
        params["country_where"] = "IN"

    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        params["page"] = page
        data = get_json(session, base_url + path, params=params, headers=headers)
        batch = data.get("data", []) if isinstance(data, dict) else []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    log.info("acled: %d events %s..%s", len(rows), start_date, end_date)
    return rows
