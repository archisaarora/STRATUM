"""Transform 1.8a — ACLED events -> raw_acled_events (incremental by date).

Credentials: either the legacy key+email or the new OAuth access token,
stored as additional secrets on the ACLED source. Leave the unused
secret(s) set to the literal string "unused".
"""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from pyspark.sql import types as T
from transforms.api import Output, incremental, transform
from transforms.external.systems import Source, external_systems

from stratum import config, sources
from stratum.core.clients import acled
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)

SCHEMA = T.StructType([
    T.StructField("event_id_cnty", T.StringType()),
    T.StructField("event_date", T.StringType()),
    T.StructField("year", T.LongType()),
    T.StructField("event_type", T.StringType()),
    T.StructField("sub_event_type", T.StringType()),
    T.StructField("country", T.StringType()),
    T.StructField("admin1", T.StringType()),
    T.StructField("location", T.StringType()),
    T.StructField("latitude", T.DoubleType()),
    T.StructField("longitude", T.DoubleType()),
    T.StructField("actor1", T.StringType()),
    T.StructField("actor2", T.StringType()),
    T.StructField("fatalities", T.LongType()),
    T.StructField("notes", T.StringType()),
    T.StructField("source", T.StringType()),
])


@incremental()
@external_systems(src=Source(sources.ACLED_SOURCE_RID))
@transform(out=Output(config.raw("raw_acled_events")))
def compute(ctx, src, out):
    conn = src.get_https_connection()
    client, base = conn.get_client(), conn.url

    def secret(name: str) -> str | None:
        try:
            v = src.get_secret(name)
            return None if v in (None, "", "unused") else v
        except Exception:
            return None

    token = secret(sources.ACLED_TOKEN_SECRET)
    key = secret(sources.ACLED_KEY_SECRET)
    email = secret(sources.ACLED_EMAIL_SECRET)

    try:
        prev = out.dataframe("previous", SCHEMA)
        max_date = prev.agg({"event_date": "max"}).collect()[0][0]
    except Exception:
        max_date = None
    start = max_date or f"{config.HISTORY_START_YEAR}-01-01"

    rows = acled.fetch_events(
        client, base,
        start_date=str(start), end_date=date.today().isoformat(),
        api_key=key, email=email, bearer_token=token,
    )
    pdf = pd.DataFrame(rows)
    for f in SCHEMA.fields:
        if f.name not in pdf.columns:
            pdf[f.name] = None
    pdf = pdf[[f.name for f in SCHEMA.fields]]
    for col in ("latitude", "longitude"):
        pdf[col] = pd.to_numeric(pdf[col], errors="coerce")
    for col in ("year", "fatalities"):
        pdf[col] = pd.to_numeric(pdf[col], errors="coerce").astype("Int64")
    # boundary-date overlap rows are deduped on event_id in clean_acled_events
    log.info("acled: %d rows from %s", len(pdf), start)
    out.write_dataframe(to_spark(ctx, pdf, SCHEMA))
