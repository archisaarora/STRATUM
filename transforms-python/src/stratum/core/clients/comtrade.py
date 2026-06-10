"""UN Comtrade clients — two access tiers, same record shape.

1. Subscription-key API (register at comtradeplus.un.org, 500 calls/day,
   100K records/call): one call covers one (reporter, year) across ALL
   defense HS codes. Preferred.
2. PUBLIC preview API (no key, no registration,
   /public/v1/preview/...): limited to ONE commodity code and ONE period
   per call, so the queue runs at (reporter, year, hs_code) grain —
   ~8x more calls, throttled. Perfect while waiting for a key.

Both queues checkpoint by what already exists in the output, so runs are
resumable and idempotent.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from stratum.core.http import get_json

log = logging.getLogger(__name__)

DATA_PATH = "/data/v1/get/C/A/HS"            # keyed: Commodities/Annual/HS
PUBLIC_PREVIEW_PATH = "/public/v1/preview/C/A/HS"  # keyless preview
WORLD_PARTNER = 0


def build_work_queue(
    reporter_m49: dict[str, int],
    years: list[int],
    done: set[tuple[str, int]],
) -> list[tuple[str, int]]:
    """Remaining (iso3, year) pairs, oldest years first for stable baselines."""
    queue = [
        (iso3, year)
        for year in sorted(years)
        for iso3 in sorted(reporter_m49)
        if (iso3, year) not in done
    ]
    return queue


def fetch_reporter_year(
    session: Any,
    base_url: str,
    api_key: str,
    *,
    reporter_m49: int,
    year: int,
    hs_codes: list[str],
    partner_detail: bool = False,
) -> list[dict]:
    """Fetch import+export rows for one reporter-year across all HS codes."""
    params = {
        "reporterCode": reporter_m49,
        "period": year,
        "cmdCode": ",".join(hs_codes),
        "flowCode": "M,X",
        "maxRecords": 100_000,
        "format": "JSON",
        "includeDesc": "true",
    }
    if not partner_detail:
        params["partnerCode"] = WORLD_PARTNER
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    data = get_json(session, base_url + DATA_PATH, params=params, headers=headers)
    return data.get("data", []) or []


def build_public_work_queue(
    reporter_m49: dict[str, int],
    years: list[int],
    hs_codes: list[str],
    done: set[tuple[str, int, str]],
) -> list[tuple[str, int, str]]:
    """Remaining (iso3, year, hs_code) triples for the keyless preview API."""
    return [
        (iso3, year, hs)
        for year in sorted(years)
        for iso3 in sorted(reporter_m49)
        for hs in hs_codes
        if (iso3, year, hs) not in done
    ]


def fetch_public_preview(
    session: Any,
    base_url: str,
    *,
    reporter_m49: int,
    year: int,
    hs_code: str,
    throttle_seconds: float = 1.0,
) -> list[dict]:
    """One keyless preview call: single reporter, single year, single HS
    code, World partner, imports+exports. Returns the same record shape as
    the keyed API. Throttled — be polite to the free endpoint."""
    params = {
        "reporterCode": reporter_m49,
        "period": year,
        "cmdCode": hs_code,          # preview limit: exactly one code
        "flowCode": "M,X",
        "partnerCode": WORLD_PARTNER,
    }
    data = get_json(session, base_url + PUBLIC_PREVIEW_PATH, params=params)
    if throttle_seconds:
        time.sleep(throttle_seconds)
    return data.get("data", []) or []


def to_raw_rows(records: list[dict], reporter_iso3: str) -> list[dict]:
    rows = []
    for r in records:
        rows.append({
            "reporter_iso3": reporter_iso3,
            "reporter_m49": r.get("reporterCode"),
            "reporter_desc": r.get("reporterDesc"),
            "partner_m49": r.get("partnerCode"),
            "partner_desc": r.get("partnerDesc"),
            "hs_code": str(r.get("cmdCode")),
            "commodity_description": r.get("cmdDesc"),
            "flow_code": r.get("flowCode"),       # M / X
            "trade_value_usd": r.get("primaryValue"),
            "net_weight_kg": r.get("netWgt"),
            "year": r.get("refYear"),
            "month": r.get("refMonth"),           # 52 == annual total
        })
    return rows
