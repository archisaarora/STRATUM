"""Transform 1.6b — raw_worldbank_indicators -> clean_worldbank_indicators.

Filters out World Bank regional aggregates (EUU, WLD, income groups…) by
keeping only ISO3 codes present in the country reference.
"""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.datasets._util import country_index_from, log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.clean("clean_worldbank_indicators")),
    raw=Input(config.raw("raw_worldbank_indicators")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(ctx, out, raw, countries):
    pdf = raw.dataframe().toPandas()
    rows_in = len(pdf)
    idx = country_index_from(countries)
    valid = set(idx.meta.index)
    pdf["country_code"] = pdf["country_iso3"].str.upper()
    pdf = pdf[pdf["country_code"].isin(valid) & pdf["value"].notna()
              & pdf["year"].notna()]
    pdf = pdf[["country_code", "year", "indicator_code", "value"]]
    pdf = pdf.drop_duplicates(subset=["country_code", "year", "indicator_code"],
                              keep="last")
    log_counts("clean_worldbank_indicators", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
