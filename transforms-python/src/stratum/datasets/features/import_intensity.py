"""Import-intensity forensics -> feature_import_intensity.

Splits each country's defense-relevant imports into direct-military vs
dual-use streams, benchmarks import intensity against declared budgets
and peers, and flags the covert-acquisition pattern (dual-use surging
while direct imports stay flat). Feeds the covert_acquisition signal rule.
"""
from __future__ import annotations

import logging

from pyspark.sql import types as T
from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.features.import_intensity import OUTPUT_COLUMNS, import_intensity
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)

_TYPES = {
    "country_code": T.StringType(),
    "year": T.LongType(),
    "top_dual_use_category": T.StringType(),
    "covert_acquisition_flag": T.BooleanType(),
}
SCHEMA = T.StructType([
    T.StructField(c, _TYPES.get(c, T.DoubleType())) for c in OUTPUT_COLUMNS
])


@transform(
    out=Output(config.features("feature_import_intensity")),
    flows=Input(config.features("feature_comtrade_with_baselines")),
    sipri=Input(config.clean("clean_sipri_milex")),
)
def compute(ctx, out, flows, sipri):
    f = flows.dataframe().toPandas()
    s = sipri.dataframe().toPandas()
    result = import_intensity(f, s)
    n_flagged = int(result["covert_acquisition_flag"].fillna(False).sum()) \
        if len(result) else 0
    if n_flagged:
        log.warning("feature_import_intensity: %d covert-acquisition flags",
                    n_flagged)
    log_counts("feature_import_intensity", len(f), len(result))
    out.write_dataframe(to_spark(ctx, result, SCHEMA))
