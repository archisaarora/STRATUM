"""Transform 4.4 — unified country threat profiles."""
from __future__ import annotations

import logging

from pyspark.sql import types as T
from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.scoring.profiles import country_threat_profiles
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)

SCHEMA = T.StructType([
    T.StructField("country_code", T.StringType()),
    T.StructField("threat_acceleration_index", T.DoubleType()),
    T.StructField("capability_credibility_score", T.DoubleType()),
    T.StructField("composite_threat_tier", T.StringType()),
    T.StructField("top_domains_of_concern", T.ArrayType(T.StringType())),
    T.StructField("active_signal_count", T.LongType()),
    T.StructField("compound_signal_count", T.LongType()),
    T.StructField("dominant_maturity_stage", T.StringType()),
    T.StructField("lead_time_min_months", T.LongType()),
    T.StructField("lead_time_max_months", T.LongType()),
    T.StructField("active_conflict", T.BooleanType()),
    T.StructField("last_signal_window", T.StringType()),
    T.StructField("last_updated", T.StringType()),
])


@transform(
    out=Output(config.scores("score_country_threat_profiles")),
    signals=Input(config.scores("threat_signals")),
    credibility=Input(config.scores("score_material_credibility")),
    classified=Input(config.features("feature_contracts_llm_classified")),
    conflict=Input(config.features("feature_conflict_intensity_monthly")),
)
def compute(ctx, out, signals, credibility, classified, conflict):
    profiles = country_threat_profiles(
        signals.dataframe().toPandas(),
        credibility.dataframe().toPandas(),
        classified.dataframe().toPandas(),
        conflict.dataframe().toPandas(),
        tier_s=config.TIER_S, tier_a=config.TIER_A, tier_b=config.TIER_B,
        lead_time_bands=config.LEAD_TIME_BANDS,
    )
    tiers = profiles["composite_threat_tier"].value_counts().to_dict() \
        if len(profiles) else {}
    log.info("country_threat_profiles: %d countries %s", len(profiles), tiers)
    out.write_dataframe(to_spark(ctx, profiles, SCHEMA))
