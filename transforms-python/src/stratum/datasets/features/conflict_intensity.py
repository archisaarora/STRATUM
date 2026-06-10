"""Transform 2.6 — GDELT daily + ACLED events -> feature_conflict_intensity_monthly."""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.features.conflict import monthly_intensity
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.features("feature_conflict_intensity_monthly")),
    gdelt=Input(config.clean("clean_gdelt_country_daily")),
    acled=Input(config.clean("clean_acled_events")),
)
def compute(ctx, out, gdelt, acled):
    g = gdelt.dataframe().toPandas()
    a = acled.dataframe().toPandas()
    result = monthly_intensity(g, a)
    log_counts("feature_conflict_intensity_monthly", len(g) + len(a), len(result))
    out.write_dataframe(to_spark(ctx, result))
