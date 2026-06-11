"""Transform 1.4 — raw_sipri_arms_transfers (uploaded exports) ->
clean_sipri_arms_transfers.

Accepts either SIPRI export format in the schema-less dataset:
  *.csv  — trade-register export (transfer-level, preferred)
  *.xlsx — TIV importer table (recipient x year totals, fallback when the
           register export misbehaves; rows are marked status='tiv_annual')
Non-state suppliers/recipients (e.g. rebel groups) keep a null country
code but retain the raw name.
"""
from __future__ import annotations

import logging

import pandas as pd
from pyspark.sql import types as T
from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.parsing import sipri_arms
from stratum.datasets._util import country_index_from, log_counts, log_unmatched, to_spark

log = logging.getLogger(__name__)

# Explicit schema: output may be empty when a placeholder (header-only)
# export is uploaded to skip this source.
SCHEMA = T.StructType([
    T.StructField("transfer_id", T.StringType()),
    T.StructField("supplier_country", T.StringType()),
    T.StructField("supplier_name_raw", T.StringType()),
    T.StructField("recipient_country", T.StringType()),
    T.StructField("recipient_name_raw", T.StringType()),
    T.StructField("weapon_designation", T.StringType()),
    T.StructField("weapon_description", T.StringType()),
    T.StructField("order_year", T.DoubleType()),
    T.StructField("quantity_ordered", T.DoubleType()),
    T.StructField("quantity_delivered", T.DoubleType()),
    T.StructField("delivery_year_last", T.DoubleType()),
    T.StructField("status", T.StringType()),
    T.StructField("tiv_per_unit", T.DoubleType()),
    T.StructField("total_tiv", T.DoubleType()),
])


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
            content = fh.read()
        try:
            frames.append(sipri_arms.parse_trade_register(content))
        except ValueError:
            try:
                frames.append(sipri_arms.parse_tiv_csv(content))
            except ValueError as exc:
                log.warning("skipped %s: %s", f.path, exc)
    for f in fs.ls(glob="**/*.xlsx"):
        with fs.open(f.path, "rb") as fh:
            frames.append(sipri_arms.parse_tiv_table(fh.read()))
    if not frames:
        raise ValueError("raw_sipri_arms_transfers contains no .csv/.xlsx "
                         "files — export from armstransfers.sipri.org first "
                         "(trade register CSV or TIV importer table XLSX)")
    pdf = pd.concat(frames, ignore_index=True)
    # Register rows + annual TIV totals together would double-count:
    # prefer the transfer-level register.
    is_annual = pdf["status"] == sipri_arms.TIV_ANNUAL_MARKER
    if is_annual.any() and (~is_annual).any():
        log.info("dropping %d annual TIV rows in favor of register detail",
                 int(is_annual.sum()))
        pdf = pdf[~is_annual]
    rows_in = len(pdf)

    idx = country_index_from(countries)
    pdf = pdf.rename(columns={"supplier": "supplier_name_raw",
                              "recipient": "recipient_name_raw"})
    pdf, un_s = idx.standardize_column(pdf, "supplier_name_raw", "supplier_country")
    pdf, un_r = idx.standardize_column(pdf, "recipient_name_raw", "recipient_country")
    log_unmatched(un_s, "sipri_arms.supplier")
    log_unmatched(un_r, "sipri_arms.recipient")

    for f_ in SCHEMA.fields:
        if f_.name not in pdf.columns:
            pdf[f_.name] = None
    pdf = pdf.drop_duplicates(subset=["transfer_id"])
    log_counts("clean_sipri_arms_transfers", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf, SCHEMA))
