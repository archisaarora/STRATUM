"""Transform 4.2 — procurement acceleration per (country, domain)."""
from __future__ import annotations

import logging

from pyspark.sql import types as T
from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.scoring.procurement_acceleration import procurement_acceleration
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)

SCHEMA = T.StructType([
    T.StructField("country_code", T.StringType()),
    T.StructField("domain", T.StringType()),
    T.StructField("window_end", T.TimestampType()),
    T.StructField("contract_count_12m", T.DoubleType()),
    T.StructField("contract_value_12m", T.DoubleType()),
    T.StructField("prior_count_12m", T.DoubleType()),
    T.StructField("prior_value_12m", T.DoubleType()),
    T.StructField("count_growth_pct", T.DoubleType()),
    T.StructField("value_growth_pct", T.DoubleType()),
    T.StructField("domain_acceleration_flag", T.BooleanType()),
    T.StructField("tempo_score", T.DoubleType()),
])


@transform(
    out=Output(config.scores("score_procurement_acceleration")),
    classified=Input(config.features("feature_contracts_llm_classified")),
)
def compute(ctx, out, classified):
    c = classified.dataframe().toPandas()
    result = procurement_acceleration(
        c,
        count_multiplier=config.ACCEL_COUNT_MULTIPLIER,
        value_growth_pct=config.ACCEL_VALUE_GROWTH_PCT,
    )
    log_counts("score_procurement_acceleration", len(c), len(result))
    out.write_dataframe(to_spark(ctx, result, SCHEMA))
