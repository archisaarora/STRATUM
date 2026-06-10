"""Shared helpers for transform wrappers (Foundry-only module)."""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)


def to_spark(ctx, pdf: pd.DataFrame, schema=None):
    """pandas -> Spark with None-safe object columns. Pass an explicit
    StructType for frames that may be empty."""
    if schema is not None:
        if len(pdf) == 0:
            return ctx.spark_session.createDataFrame([], schema)
        return ctx.spark_session.createDataFrame(pdf, schema)
    pdf = pdf.where(pd.notnull(pdf), None)
    return ctx.spark_session.createDataFrame(pdf)


def country_index_from(ref_input) -> "CountryIndex":  # noqa: F821
    """Build a CountryIndex from the ref_country_iso_lookup Input."""
    from stratum.core.countries import CountryIndex

    return CountryIndex.from_reference(ref_input.dataframe().toPandas())


def log_unmatched(unmatched: pd.DataFrame, source: str) -> None:
    """Quality requirement: surface country-standardization misses."""
    if len(unmatched):
        examples = unmatched.iloc[:, 0].head(15).tolist()
        log.warning("%s: %d unmatched country names (add aliases to "
                    "ref_country_iso_lookup): %s", source, len(unmatched), examples)


def log_counts(source: str, rows_in: int, rows_out: int) -> None:
    log.info("%s: rows_in=%d rows_out=%d dropped=%d",
             source, rows_in, rows_out, rows_in - rows_out)


def previous_ids(out, schema, id_col: str) -> set[str]:
    """IDs already present in an incremental output (never reprocess)."""
    try:
        prev = out.dataframe("previous", schema)
        return {r[id_col] for r in prev.select(id_col).distinct().collect()}
    except Exception as exc:  # first run / snapshot fallback
        log.info("no previous output readable (%s) — treating as first run", exc)
        return set()
