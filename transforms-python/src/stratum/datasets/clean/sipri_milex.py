"""Transform 1.3 — raw_sipri_milex (uploaded .xlsx files) -> clean_sipri_milex.

Upload the SIPRI milex workbook(s) from sipri.org/databases/milex into the
schema-less dataset `raw_sipri_milex` (Dataset > Import > local files,
"keep as files"). This transform parses every .xlsx in the dataset.

Output (long format): country_code, country_name, year, measure, value
  measure in {expenditure_current_usd, expenditure_constant_usd,
              expenditure_pct_gdp}; USD values are absolute (not millions).
"""
from __future__ import annotations

import logging

import pandas as pd
from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.parsing import sipri_milex
from stratum.datasets._util import country_index_from, log_counts, log_unmatched, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.clean("clean_sipri_milex")),
    raw=Input(config.raw("raw_sipri_milex")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(ctx, out, raw, countries):
    fs = raw.filesystem()
    frames = []
    for f in fs.ls(glob="**/*.xlsx"):
        with fs.open(f.path, "rb") as fh:
            frames.append(sipri_milex.parse_workbook(fh.read()))
    if not frames:
        raise ValueError("raw_sipri_milex contains no .xlsx files — upload the "
                         "SIPRI milex workbook first (docs/01_DATA_ACQUISITION.md)")
    pdf = pd.concat(frames, ignore_index=True)
    rows_in = len(pdf)

    idx = country_index_from(countries)
    pdf, unmatched = idx.standardize_column(pdf, "country_name_raw", "country_code")
    log_unmatched(unmatched, "sipri_milex")
    pdf = pdf[pdf["country_code"].notna()]
    pdf["country_name"] = pdf["country_code"].map(idx.name_of)
    pdf = pdf[pdf["year"] >= config.WORLDBANK_START_YEAR]
    pdf = (pdf[["country_code", "country_name", "year", "measure", "value"]]
           .drop_duplicates(subset=["country_code", "year", "measure"], keep="last"))
    log_counts("clean_sipri_milex", rows_in, len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
