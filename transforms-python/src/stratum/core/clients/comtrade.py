"""UN Comtrade+ client (comtradeapi.un.org, free tier: 500 calls/day).

One call = one (reporter, year) pulling all defense-relevant HS codes for
imports+exports against the World aggregate. A work queue with
checkpointing keeps each run inside the daily call budget; the checkpoint
is simply the set of (reporter, year) pairs already present in the output
dataset, so the transform is idempotent and resumes automatically.
"""
from __future__ import annotations

import logging
from typing import Any

from stratum.core.http import get_json

log = logging.getLogger(__name__)

DATA_PATH = "/data/v1/get/C/A/HS"  # Commodities / Annual / HS classification
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
