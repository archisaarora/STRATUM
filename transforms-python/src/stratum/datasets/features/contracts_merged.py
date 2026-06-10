"""Transform 2.3 — clean_usaspending_contracts + clean_dod_contracts ->
feature_contracts_merged."""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.features.contracts import merge_contract_sources
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.features("feature_contracts_merged")),
    usas=Input(config.clean("clean_usaspending_contracts")),
    dod=Input(config.clean("clean_dod_contracts")),
)
def compute(ctx, out, usas, dod):
    u = usas.dataframe().toPandas()
    d = dod.dataframe().toPandas()
    merged = merge_contract_sources(u, d)
    log_counts("feature_contracts_merged", len(u) + len(d), len(merged))
    out.write_dataframe(to_spark(ctx, merged))
