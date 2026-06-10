"""Transform 1.5b — raw_comtrade_flows -> clean_comtrade_flows.

Maps M49 partner codes to ISO3 (reporter is already ISO3 from ingest),
turns flow codes into import/export, and keeps annual rows.
"""
from __future__ import annotations

import logging

import pandas as pd
from transforms.api import Input, Output, transform

from stratum import config
from stratum.datasets._util import country_index_from, log_counts, to_spark

log = logging.getLogger(__name__)

FLOWS = {"M": "import", "X": "export"}


@transform(
    out=Output(config.clean("clean_comtrade_flows")),
    raw=Input(config.raw("raw_comtrade_flows")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(ctx, out, raw, countries):
    pdf = raw.dataframe().toPandas()
    rows_in = len(pdf)
    pdf = pdf[pdf["hs_code"].notna()]  # drop empty checkpoint markers

    idx = country_index_from(countries)
    pdf["partner_country"] = pdf["partner_m49"].map(
        lambda v: "WLD" if pd.notna(v) and int(v) == 0 else idx.to_iso3(v))
    pdf["flow_direction"] = pdf["flow_code"].map(FLOWS)
    pdf = pdf[pdf["flow_direction"].notna()]

    pdf = pdf.rename(columns={"reporter_iso3": "reporter_country",
                              "commodity_description": "commodity_description_raw"})
    pdf["is_world_total"] = pdf["partner_country"] == "WLD"
    pdf = pdf[["reporter_country", "partner_country", "is_world_total",
               "hs_code", "commodity_description_raw", "flow_direction",
               "trade_value_usd", "net_weight_kg", "year", "month"]]
    pdf = pdf.drop_duplicates(
        subset=["reporter_country", "partner_country", "hs_code",
                "flow_direction", "year", "month"], keep="last")
    log_counts("clean_comtrade_flows", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
