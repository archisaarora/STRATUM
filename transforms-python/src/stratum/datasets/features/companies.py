"""Company rollup with OpenSanctions cross-reference -> feature_companies."""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.features.contracts import company_rollup
from stratum.core.parsing.opensanctions import build_org_name_index
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.features("feature_companies")),
    classified=Input(config.features("feature_contracts_llm_classified")),
    sanctions=Input(config.clean("clean_opensanctions")),
)
def compute(ctx, out, classified, sanctions):
    contracts = classified.dataframe().toPandas()
    org_names = build_org_name_index(sanctions.dataframe().toPandas())
    companies = company_rollup(contracts, org_names)
    n_sanctioned = int(companies["opensanctions_match"].sum())
    if n_sanctioned:
        log.warning("feature_companies: %d contract recipients match "
                    "OpenSanctions entities", n_sanctioned)
    log_counts("feature_companies", len(contracts), len(companies))
    out.write_dataframe(to_spark(ctx, companies))
