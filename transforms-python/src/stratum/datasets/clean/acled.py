"""Transform 1.8b — raw_acled_events -> clean_acled_events."""
from __future__ import annotations

import logging

import pandas as pd
from pyspark.sql import types as T
from transforms.api import Input, Output, transform

from stratum import config
from stratum.datasets._util import country_index_from, log_counts, log_unmatched, to_spark

log = logging.getLogger(__name__)

# Explicit schema: output may be empty when this source is skipped via a
# placeholder upload (docs/01_DATA_ACQUISITION.md).
SCHEMA = T.StructType([
    T.StructField("event_id", T.StringType()),
    T.StructField("event_date", T.TimestampType()),
    T.StructField("country_code", T.StringType()),
    T.StructField("country", T.StringType()),
    T.StructField("event_type", T.StringType()),
    T.StructField("sub_event_type", T.StringType()),
    T.StructField("admin1", T.StringType()),
    T.StructField("location", T.StringType()),
    T.StructField("latitude", T.DoubleType()),
    T.StructField("longitude", T.DoubleType()),
    T.StructField("actor1", T.StringType()),
    T.StructField("actor2", T.StringType()),
    T.StructField("fatalities", T.DoubleType()),
    T.StructField("notes", T.StringType()),
])


@transform(
    out=Output(config.clean("clean_acled_events")),
    raw=Input(config.raw("raw_acled_events")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(ctx, out, raw, countries):
    pdf = raw.dataframe().toPandas()
    rows_in = len(pdf)
    idx = country_index_from(countries)
    pdf, unmatched = idx.standardize_column(pdf, "country", "country_code")
    log_unmatched(unmatched, "acled")
    pdf = pdf[pdf["country_code"].notna()]
    pdf["event_date"] = pd.to_datetime(pdf["event_date"], errors="coerce")
    pdf = pdf.rename(columns={"event_id_cnty": "event_id"})
    pdf = pdf[pdf["event_date"].notna()].drop_duplicates(subset=["event_id"],
                                                         keep="last")
    for col in ("latitude", "longitude"):
        pdf[col] = pd.to_numeric(pdf[col], errors="coerce")
    pdf["fatalities"] = pd.to_numeric(pdf["fatalities"], errors="coerce").fillna(0)
    log_counts("clean_acled_events", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf, SCHEMA))
