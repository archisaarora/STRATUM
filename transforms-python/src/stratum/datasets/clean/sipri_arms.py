"""Transform 1.4 — raw_sipri_arms_transfers (uploaded CSV export) ->
clean_sipri_arms_transfers.

Upload the trade-register CSV from armstransfers.sipri.org (all years,
all countries) into the schema-less dataset `raw_sipri_arms_transfers`.
Non-state suppliers/recipients (e.g. rebel groups) keep a null country
code but retain the raw name.
"""
from __future__ import annotations

import logging

import pandas as pd
from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.parsing import sipri_arms
from stratum.datasets._util import country_index_from, log_counts, log_unmatched, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.clean("clean_sipri_arms_transfers")),
    raw=Input(config.raw("raw_sipri_arms_transfers")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(ctx, out, raw, countries):
    fs = raw.filesystem()
    frames = []
    for f in fs.ls(glob="**/*.csv"):
        with fs.open(f.path, "rb") as fh:
            frames.append(sipri_arms.parse_trade_register(fh.read()))
    if not frames:
        raise ValueError("raw_sipri_arms_transfers contains no .csv files — "
                         "export from armstransfers.sipri.org first")
    pdf = pd.concat(frames, ignore_index=True)
    rows_in = len(pdf)

    idx = country_index_from(countries)
    pdf = pdf.rename(columns={"supplier": "supplier_name_raw",
                              "recipient": "recipient_name_raw"})
    pdf, un_s = idx.standardize_column(pdf, "supplier_name_raw", "supplier_country")
    pdf, un_r = idx.standardize_column(pdf, "recipient_name_raw", "recipient_country")
    log_unmatched(un_s, "sipri_arms.supplier")
    log_unmatched(un_r, "sipri_arms.recipient")

    cols = ["transfer_id", "supplier_country", "supplier_name_raw",
            "recipient_country", "recipient_name_raw", "weapon_designation",
            "weapon_description", "order_year", "quantity_ordered",
            "quantity_delivered", "delivery_year_last", "status",
            "tiv_per_unit", "total_tiv"]
    for c in cols:
        if c not in pdf.columns:
            pdf[c] = None
    pdf = pdf[cols].drop_duplicates(subset=["transfer_id"])
    log_counts("clean_sipri_arms_transfers", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
