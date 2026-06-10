"""Transform 1.2 — defense.gov contract announcement scraper (incremental).

Schedule daily ~06:00 UTC. Each run walks the listing pages, skips article
URLs already ingested, and appends newly parsed contract paragraphs.
"""
from __future__ import annotations

import logging

import pandas as pd
from pyspark.sql import types as T
from transforms.api import Output, incremental, transform
from transforms.external.systems import Source, external_systems

from stratum import config, sources
from stratum.core.clients import dod
from stratum.datasets._util import previous_ids, to_spark

log = logging.getLogger(__name__)

SCHEMA = T.StructType([
    T.StructField("contract_id", T.StringType()),
    T.StructField("announcement_date_text", T.StringType()),
    T.StructField("contractor_name", T.StringType()),
    T.StructField("contract_value_usd", T.DoubleType()),
    T.StructField("description_text", T.StringType()),
    T.StructField("contracting_command", T.StringType()),
    T.StructField("contracting_activity", T.StringType()),
    T.StructField("source_url", T.StringType()),
])

FIRST_RUN_PAGES = 40   # ~1 year of daily announcements
DAILY_PAGES = 3


@incremental()
@external_systems(defgov=Source(sources.DEFENSE_GOV_SOURCE_RID))
@transform(out=Output(config.raw("raw_dod_contracts_daily")))
def compute(ctx, defgov, out):
    client = defgov.get_https_connection().get_client()
    base = defgov.get_https_connection().url

    known = previous_ids(out, SCHEMA, "source_url")
    pages = DAILY_PAGES if known else FIRST_RUN_PAGES
    rows = dod.fetch_recent_contracts(client, base, max_pages=pages, known_urls=known)
    log.info("dod scraper: %d new contract rows (known urls: %d)", len(rows), len(known))

    pdf = pd.DataFrame(rows, columns=[f.name for f in SCHEMA.fields])
    out.write_dataframe(to_spark(ctx, pdf, SCHEMA))
