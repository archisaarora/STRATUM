"""Transform 4.1 — Material Credibility Score per (country, domain, year)."""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.scoring.material_credibility import material_credibility
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.scores("score_material_credibility")),
    flows=Input(config.features("feature_comtrade_with_baselines")),
    sipri=Input(config.clean("clean_sipri_milex")),
    classified=Input(config.features("feature_contracts_llm_classified")),
)
def compute(ctx, out, flows, sipri, classified):
    f = flows.dataframe().toPandas()
    s = sipri.dataframe().toPandas()
    c = classified.dataframe().toPandas()
    result = material_credibility(f, s, c)
    log_counts("score_material_credibility", len(f), len(result))
    out.write_dataframe(to_spark(ctx, result))
