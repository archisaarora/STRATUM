"""Transform 1.1a — USASpending API -> raw_usaspending_contracts (incremental).

External Transform: requires a REST API source for api.usaspending.gov
(no credential) imported into this repo — paste its RID in stratum/sources.py.

Each run ingests forward from the last ingested window end (or
HISTORY_START_YEAR on first run), in monthly windows, capped by
USASPENDING_MAX_PAGES_PER_RUN. Re-runs are idempotent: the clean transform
dedupes on award_id, and windows resume from the previous max.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from pyspark.sql import types as T
from transforms.api import Output, incremental, transform
from transforms.external.systems import Source, external_systems
# Legacy enrollments without REST sources can use:
#   from transforms.external.systems import use_external_systems, EgressPolicy

from stratum import config, sources
from stratum.core.clients import usaspending
from stratum.datasets._util import previous_ids, to_spark

log = logging.getLogger(__name__)

SCHEMA = T.StructType([
    T.StructField("award_id", T.StringType()),
    T.StructField("display_award_id", T.StringType()),
    T.StructField("recipient_name", T.StringType()),
    T.StructField("recipient_country_code", T.StringType()),
    T.StructField("awarding_agency_name", T.StringType()),
    T.StructField("awarding_sub_agency", T.StringType()),
    T.StructField("funding_agency_name", T.StringType()),
    T.StructField("award_description", T.StringType()),
    T.StructField("total_obligated_amount", T.DoubleType()),
    T.StructField("period_of_performance_start_date", T.StringType()),
    T.StructField("period_of_performance_current_end_date", T.StringType()),
    T.StructField("naics_code", T.StringType()),
    T.StructField("product_or_service_code", T.StringType()),
    T.StructField("pop_country_code", T.StringType()),
    T.StructField("ingest_window_start", T.StringType()),
    T.StructField("ingest_window_end", T.StringType()),
])


@incremental()
@external_systems(usas=Source(sources.USASPENDING_SOURCE_RID))
@transform(out=Output(config.raw("raw_usaspending_contracts")))
def compute(ctx, usas, out):
    client = usas.get_https_connection().get_client()
    base = usas.get_https_connection().url

    done_windows = previous_ids(out, SCHEMA, "ingest_window_start")
    cursor = date(config.HISTORY_START_YEAR, 1, 1)
    today = date.today()
    rows: list[dict] = []
    windows_this_run = 0

    while cursor < today and windows_this_run < 6:  # up to 6 months per build
        window_end = min(_month_end(cursor), today)
        ws, we = cursor.isoformat(), window_end.isoformat()
        if ws not in done_windows:
            records = list(usaspending.iter_awards(
                client, base,
                start_date=ws, end_date=we,
                agencies=config.USASPENDING_AGENCIES,
                award_type_codes=config.USASPENDING_AWARD_TYPES,
                page_limit=config.USASPENDING_PAGE_LIMIT,
                max_pages=config.USASPENDING_MAX_PAGES_PER_RUN,
            ))
            rows.extend(usaspending.to_raw_rows(records, ws, we))
            windows_this_run += 1
            log.info("usaspending window %s..%s -> %d awards", ws, we, len(records))
        cursor = window_end + timedelta(days=1)

    pdf = pd.DataFrame(rows, columns=[f.name for f in SCHEMA.fields])
    if "total_obligated_amount" in pdf:
        pdf["total_obligated_amount"] = pd.to_numeric(
            pdf["total_obligated_amount"], errors="coerce")
    out.write_dataframe(to_spark(ctx, pdf, SCHEMA))


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
    return nxt - timedelta(days=1)
