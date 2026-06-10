"""Transform 1.2b — raw_dod_contracts_daily -> clean_dod_contracts."""
from __future__ import annotations

import logging

import pandas as pd
from transforms.api import Input, Output, transform

from stratum import config
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.clean("clean_dod_contracts")),
    raw=Input(config.raw("raw_dod_contracts_daily")),
)
def compute(ctx, out, raw):
    pdf = raw.dataframe().toPandas()
    rows_in = len(pdf)
    pdf["contract_date"] = pd.to_datetime(
        pdf["announcement_date_text"], format="mixed", errors="coerce")
    pdf["contract_value_usd"] = pd.to_numeric(pdf["contract_value_usd"], errors="coerce")
    pdf = pdf[pdf["description_text"].notna() & pdf["contract_value_usd"].notna()]
    pdf = pdf.drop_duplicates(subset=["contract_id"])
    pdf["recipient_country"] = "USA"
    pdf = pdf[["contract_id", "contract_date", "contractor_name",
               "recipient_country", "contract_value_usd", "description_text",
               "contracting_command", "contracting_activity", "source_url"]]
    log_counts("clean_dod_contracts", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
