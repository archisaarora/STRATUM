"""Transform 1.7 — raw_gdelt_events -> clean_gdelt_country_daily (PySpark).

Expected raw shape: the BigQuery aggregation produced by
scripts/local_fetch.py gdelt (or an equivalent Data Connection BigQuery
sync) with columns: event_date_int, actor1_country, event_root_code,
event_count, avg_goldstein, total_mentions, total_sources.

Output: one row per (country_code, date) with total + conflict-coded event
counts and mention-weighted Goldstein average. GDELT/CAMEO country codes
are ISO3-style; codes that don't resolve are dropped (logged volume).
"""
from __future__ import annotations

from pyspark.sql import functions as F
from transforms.api import Input, Output, transform_df

from stratum import config

CONFLICT_ROOTS = ["13", "14", "15", "17", "18", "19", "20"]


@transform_df(
    Output(config.clean("clean_gdelt_country_daily")),
    raw=Input(config.raw("raw_gdelt_events")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(raw, countries):
    valid = countries.select(F.col("iso3").alias("country_code"))
    df = (
        raw
        .withColumn("date", F.to_date(F.col("event_date_int").cast("string"),
                                      "yyyyMMdd"))
        .withColumn("country_code", F.upper(F.col("actor1_country")))
        .withColumn("root", F.lpad(F.col("event_root_code").cast("string"), 2, "0"))
        .where(F.col("date").isNotNull())
        .join(F.broadcast(valid), "country_code", "inner")
    )
    return (
        df.groupBy("country_code", "date")
        .agg(
            F.sum("event_count").alias("event_count"),
            F.sum(F.when(F.col("root").isin(CONFLICT_ROOTS),
                         F.col("event_count")).otherwise(0))
             .alias("conflict_event_count"),
            (F.sum(F.col("avg_goldstein") * F.col("event_count"))
             / F.sum("event_count")).alias("avg_goldstein"),
            F.sum("total_mentions").alias("total_mentions"),
        )
    )
