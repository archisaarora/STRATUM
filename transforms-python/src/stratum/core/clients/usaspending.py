"""USASpending.gov client — POST /api/v2/search/spending_by_award/.

Free REST API, no key. Pulls contract awards (type codes A–D) with the
free-text description field that Layer 1 feeds to the LLM.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

from stratum.core.http import post_json

log = logging.getLogger(__name__)

SEARCH_PATH = "/api/v2/search/spending_by_award/"

FIELDS = [
    "Award ID", "Recipient Name", "Description", "Award Amount",
    "Awarding Agency", "Awarding Sub Agency", "Funding Agency",
    "Start Date", "End Date", "NAICS", "PSC",
    "Recipient Location", "Place of Performance Country Code",
    "recipient_id", "generated_internal_id",
]


def iter_awards(
    session: Any,
    base_url: str,
    *,
    start_date: str,
    end_date: str,
    agencies: list[str],
    award_type_codes: list[str],
    page_limit: int = 100,
    max_pages: int = 400,
) -> Iterator[dict]:
    """Yield raw award records for one date window. Paginates until exhausted
    or max_pages (caller checkpoints by date window for incremental runs)."""
    filters: dict[str, Any] = {
        "time_period": [{"start_date": start_date, "end_date": end_date}],
        "award_type_codes": award_type_codes,
    }
    if agencies:
        filters["agencies"] = [
            {"type": "awarding", "tier": "toptier", "name": a} for a in agencies
        ]
    page = 1
    while page <= max_pages:
        body = {
            "filters": filters,
            "fields": FIELDS,
            "page": page,
            "limit": page_limit,
            "sort": "Start Date",
            "order": "desc",
            "subawards": False,
        }
        data = post_json(session, base_url + SEARCH_PATH, json=body)
        results = data.get("results", [])
        for r in results:
            yield r
        meta = data.get("page_metadata", {})
        if not meta.get("hasNext") or not results:
            break
        page += 1
    log.info("usaspending: window %s..%s fetched %d pages", start_date, end_date, page)


def to_raw_rows(records: list[dict], window_start: str, window_end: str) -> list[dict]:
    """Map API records to the raw_usaspending_contracts schema."""
    rows = []
    for r in records:
        loc = r.get("Recipient Location") or {}
        rows.append({
            "award_id": r.get("generated_internal_id") or r.get("Award ID"),
            "display_award_id": r.get("Award ID"),
            "recipient_name": r.get("Recipient Name"),
            "recipient_country_code": (loc.get("country_code")
                                       if isinstance(loc, dict) else None),
            "awarding_agency_name": r.get("Awarding Agency"),
            "awarding_sub_agency": r.get("Awarding Sub Agency"),
            "funding_agency_name": r.get("Funding Agency"),
            "award_description": r.get("Description"),
            "total_obligated_amount": r.get("Award Amount"),
            "period_of_performance_start_date": r.get("Start Date"),
            "period_of_performance_current_end_date": r.get("End Date"),
            "naics_code": r.get("NAICS"),
            "product_or_service_code": r.get("PSC"),
            "pop_country_code": r.get("Place of Performance Country Code"),
            "ingest_window_start": window_start,
            "ingest_window_end": window_end,
        })
    return rows
