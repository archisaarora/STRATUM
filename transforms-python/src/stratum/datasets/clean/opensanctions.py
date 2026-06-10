"""Transform 1.9b — raw_opensanctions_entities -> clean_opensanctions.

Handles both raw shapes (API-ingested tidy rows or a manually uploaded
targets.simple.csv with original column names).
"""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.parsing.opensanctions import tidy_targets
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.clean("clean_opensanctions")),
    raw=Input(config.raw("raw_opensanctions_entities")),
)
def compute(ctx, out, raw):
    pdf = raw.dataframe().toPandas()
    rows_in = len(pdf)
    pdf = tidy_targets(pdf)
    pdf = pdf.drop_duplicates(subset=["entity_id"], keep="last")
    log_counts("clean_opensanctions", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
