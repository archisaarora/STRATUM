"""Transform 4.2 — procurement acceleration per (country, domain)."""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.scoring.procurement_acceleration import procurement_acceleration
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


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
    out.write_dataframe(to_spark(ctx, result))
