"""Transform 2.4 — SIPRI vs World Bank milex -> feature_budget_discrepancy."""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.features.budget import budget_discrepancy
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.features("feature_budget_discrepancy")),
    sipri=Input(config.clean("clean_sipri_milex")),
    wb=Input(config.clean("clean_worldbank_indicators")),
)
def compute(ctx, out, sipri, wb):
    s = sipri.dataframe().toPandas()
    w = wb.dataframe().toPandas()
    result = budget_discrepancy(s, w, flag_pct=config.BUDGET_DISCREPANCY_FLAG_PCT)
    log_counts("feature_budget_discrepancy", len(s), len(result))
    out.write_dataframe(to_spark(ctx, result))
