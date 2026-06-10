"""Transform 1.6a — World Bank indicators -> raw_worldbank_indicators.

Snapshot transform: the full pull is only ~8 indicators x all countries,
so each run refreshes everything (simplest possible idempotency).
No credential needed — the source just provides egress.
"""
from __future__ import annotations

import logging

import pandas as pd
from transforms.api import Output, transform
from transforms.external.systems import Source, external_systems

from stratum import config, sources
from stratum.core.clients import worldbank
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)


@external_systems(wb=Source(sources.WORLDBANK_SOURCE_RID))
@transform(out=Output(config.raw("raw_worldbank_indicators")))
def compute(ctx, wb, out):
    client = wb.get_https_connection().get_client()
    base = wb.get_https_connection().url

    rows: list[dict] = []
    end_year = pd.Timestamp.now().year
    for indicator in config.WORLDBANK_INDICATORS:
        rows.extend(worldbank.fetch_indicator(
            client, base, indicator,
            start_year=config.WORLDBANK_START_YEAR, end_year=end_year,
        ))
    pdf = pd.DataFrame(rows)
    pdf["value"] = pd.to_numeric(pdf["value"], errors="coerce")
    pdf["year"] = pd.to_numeric(pdf["year"], errors="coerce").astype("Int64")
    log.info("worldbank: %d indicator rows", len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
