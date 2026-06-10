"""Transform 2.5 — clean_sipri_arms_transfers -> feature_arms_transfer_velocity."""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.features.arms_velocity import transfer_velocity
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.features("feature_arms_transfer_velocity")),
    transfers=Input(config.clean("clean_sipri_arms_transfers")),
)
def compute(ctx, out, transfers):
    pdf = transfers.dataframe().toPandas()
    pdf = pdf[pdf["recipient_country"].notna()]
    result = transfer_velocity(
        pdf,
        window_years=config.ROLLING_BASELINE_YEARS,
        spike_multiplier=config.ARMS_SPIKE_MULTIPLIER,
    )
    log_counts("feature_arms_transfer_velocity", len(pdf), len(result))
    out.write_dataframe(to_spark(ctx, result))
