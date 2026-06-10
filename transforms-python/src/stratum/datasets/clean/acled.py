"""Transform 1.8b — raw_acled_events -> clean_acled_events."""
from __future__ import annotations

import logging

import pandas as pd
from transforms.api import Input, Output, transform

from stratum import config
from stratum.datasets._util import country_index_from, log_counts, log_unmatched, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.clean("clean_acled_events")),
    raw=Input(config.raw("raw_acled_events")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(ctx, out, raw, countries):
    pdf = raw.dataframe().toPandas()
    rows_in = len(pdf)
    idx = country_index_from(countries)
    pdf, unmatched = idx.standardize_column(pdf, "country", "country_code")
    log_unmatched(unmatched, "acled")
    pdf = pdf[pdf["country_code"].notna()]
    pdf["event_date"] = pd.to_datetime(pdf["event_date"], errors="coerce")
    pdf["fatalities"] = pd.to_numeric(pdf["fatalities"], errors="coerce").fillna(0)
    pdf = pdf.rename(columns={"event_id_cnty": "event_id"})
    pdf = pdf[["event_id", "event_date", "country_code", "country", "event_type",
               "sub_event_type", "admin1", "location", "latitude", "longitude",
               "actor1", "actor2", "fatalities", "notes"]]
    pdf = pdf[pdf["event_date"].notna()].drop_duplicates(subset=["event_id"],
                                                         keep="last")
    log_counts("clean_acled_events", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
