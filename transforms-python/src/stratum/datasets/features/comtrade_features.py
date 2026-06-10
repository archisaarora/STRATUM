"""Transforms 2.2 + 2.1 — capability mapping, then rolling baselines.

feature_comtrade_capability_mapped: every clean flow row + capability domain
feature_comtrade_with_baselines: annual (reporter, hs, flow) grain with
3-year rolling baseline, deviation %, and anomaly score. Uses World-total
rows when present; otherwise sums partner-level rows.
"""
from __future__ import annotations

import logging

from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.features import baselines
from stratum.datasets._util import log_counts, to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.features("feature_comtrade_capability_mapped")),
    flows=Input(config.clean("clean_comtrade_flows")),
    hs_ref=Input(config.reference("ref_hs_capability_mapping")),
)
def map_capability(ctx, out, flows, hs_ref):
    pdf = flows.dataframe().toPandas()
    mapped = baselines.map_capability(pdf, hs_ref.dataframe().toPandas())
    log_counts("feature_comtrade_capability_mapped", len(pdf), len(mapped))
    out.write_dataframe(to_spark(ctx, mapped))


@transform(
    out=Output(config.features("feature_comtrade_with_baselines")),
    mapped=Input(config.features("feature_comtrade_capability_mapped")),
)
def with_baselines(ctx, out, mapped):
    pdf = mapped.dataframe().toPandas()
    world = pdf[pdf["is_world_total"]] if "is_world_total" in pdf else pdf
    use = world if len(world) else pdf[pdf["partner_country"] != "WLD"]
    annual = baselines.annual_with_baselines(
        use,
        window_years=config.ROLLING_BASELINE_YEARS,
        anomaly_flag_pct=config.BASELINE_ANOMALY_FLAG_PCT,
    )
    log_counts("feature_comtrade_with_baselines", len(pdf), len(annual))
    out.write_dataframe(to_spark(ctx, annual))
