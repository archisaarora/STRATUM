"""Transform 1.5a — UN Comtrade ingestion queue (incremental, rate-limited).

One API call covers one (reporter, year) for all defense HS codes. The
free tier allows 500 calls/day, so the transform processes up to
COMTRADE_DAILY_CALL_BUDGET pending pairs per run and checkpoints simply by
what already exists in the output. Schedule daily until the backlog
(len(TARGET_COUNTRIES) x years) drains, then monthly.

Source setup: REST source for comtradeapi.un.org with the API key stored
as additional secret `ComtradeApiKey` (see stratum/sources.py).
"""
from __future__ import annotations

import logging

import pandas as pd
from pyspark.sql import types as T
from transforms.api import Input, Output, incremental, transform
from transforms.external.systems import Source, external_systems

from stratum import config, sources
from stratum.core.clients import comtrade
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)

SCHEMA = T.StructType([
    T.StructField("reporter_iso3", T.StringType()),
    T.StructField("reporter_m49", T.LongType()),
    T.StructField("reporter_desc", T.StringType()),
    T.StructField("partner_m49", T.LongType()),
    T.StructField("partner_desc", T.StringType()),
    T.StructField("hs_code", T.StringType()),
    T.StructField("commodity_description", T.StringType()),
    T.StructField("flow_code", T.StringType()),
    T.StructField("trade_value_usd", T.DoubleType()),
    T.StructField("net_weight_kg", T.DoubleType()),
    T.StructField("year", T.LongType()),
    T.StructField("month", T.LongType()),
    T.StructField("checkpoint_key", T.StringType()),
])


@incremental(snapshot_inputs=["countries"])
@external_systems(un=Source(sources.COMTRADE_SOURCE_RID))
@transform(
    out=Output(config.raw("raw_comtrade_flows")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(ctx, un, out, countries):
    client = un.get_https_connection().get_client()
    base = un.get_https_connection().url
    api_key = un.get_secret(sources.COMTRADE_KEY_SECRET)

    ref = countries.dataframe().toPandas()
    m49 = dict(zip(ref["iso3"], ref["m49_code"].astype(int)))
    m49.update(config.COMTRADE_SPECIAL_M49)
    reporters = {c: m49[c] for c in config.TARGET_COUNTRIES if c in m49}

    try:
        prev = out.dataframe("previous", SCHEMA)
        done = {(r.reporter_iso3, int(r.year))
                for r in prev.select("reporter_iso3", "year").distinct().collect()}
    except Exception:
        done = set()

    years = list(range(config.HISTORY_START_YEAR, pd.Timestamp.now().year + 1))
    queue = comtrade.build_work_queue(reporters, years, done)
    budget = min(len(queue), config.COMTRADE_DAILY_CALL_BUDGET)
    log.info("comtrade queue: %d pending, processing %d this run", len(queue), budget)

    rows: list[dict] = []
    for iso3, year in queue[:budget]:
        try:
            records = comtrade.fetch_reporter_year(
                client, base, api_key,
                reporter_m49=reporters[iso3], year=year,
                hs_codes=config.DEFENSE_HS_CODES,
                partner_detail=config.COMTRADE_PARTNER_DETAIL,
            )
        except RuntimeError as exc:
            log.warning("comtrade %s/%s failed after retries: %s — will retry "
                        "next run", iso3, year, exc)
            continue
        batch = comtrade.to_raw_rows(records, iso3)
        for b in batch:
            b["checkpoint_key"] = f"{iso3}:{year}"
        # Mark empty-but-successful pulls so they aren't refetched forever.
        if not batch:
            rows.append({"reporter_iso3": iso3, "year": year,
                         "checkpoint_key": f"{iso3}:{year}"})
        rows.extend(batch)

    pdf = pd.DataFrame(rows, columns=[f.name for f in SCHEMA.fields])
    for col, typ in [("trade_value_usd", float), ("net_weight_kg", float)]:
        pdf[col] = pd.to_numeric(pdf[col], errors="coerce")
    for col in ("reporter_m49", "partner_m49", "year", "month"):
        pdf[col] = pd.to_numeric(pdf[col], errors="coerce").astype("Int64")
    out.write_dataframe(to_spark(ctx, pdf, SCHEMA))
