"""Transform 4.3 — the ThreatSignal generation engine.

Reads every scored feature dataset and emits discrete signals (including
compound signals). Deterministic signal IDs keep re-runs idempotent; the
output backs the ThreatSignal object type.
"""
from __future__ import annotations

import logging

from pyspark.sql import types as T
from transforms.api import Input, Output, transform

from stratum import config
from stratum.core.scoring.signals import generate_all_signals
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)

SCHEMA = T.StructType([
    T.StructField("signal_id", T.StringType()),
    T.StructField("signal_type", T.StringType()),
    T.StructField("country_code", T.StringType()),
    T.StructField("domain", T.StringType()),
    T.StructField("signal_strength", T.DoubleType()),
    T.StructField("confidence_score", T.DoubleType()),
    T.StructField("description_text", T.StringType()),
    T.StructField("supporting_evidence", T.ArrayType(T.StringType())),
    T.StructField("window_end", T.StringType()),
    T.StructField("created_at", T.StringType()),
    T.StructField("reviewed", T.BooleanType()),
    T.StructField("analyst_notes", T.StringType()),
])


@transform(
    out=Output(config.scores("threat_signals")),
    flows=Input(config.features("feature_comtrade_with_baselines")),
    accel=Input(config.scores("score_procurement_acceleration")),
    budget=Input(config.features("feature_budget_discrepancy")),
    credibility=Input(config.scores("score_material_credibility")),
    velocity=Input(config.features("feature_arms_transfer_velocity")),
    intensity=Input(config.features("feature_import_intensity")),
)
def compute(ctx, out, flows, accel, budget, credibility, velocity, intensity):
    signals = generate_all_signals(
        flows=flows.dataframe().toPandas(),
        accel=accel.dataframe().toPandas(),
        budget=budget.dataframe().toPandas(),
        credibility=credibility.dataframe().toPandas(),
        velocity=velocity.dataframe().toPandas(),
        intensity=intensity.dataframe().toPandas(),
        thresholds={
            "material_min_score": config.SIGNAL_MATERIAL_MIN_SCORE,
            "material_min_deviation": config.SIGNAL_MATERIAL_MIN_DEVIATION,
            "underdeclaration_min": config.UNDERDECLARATION_SIGNAL_MIN,
            "compound_escalation": config.COMPOUND_ESCALATION,
        },
    )
    by_type = signals["signal_type"].value_counts().to_dict() if len(signals) else {}
    log.info("threat_signals: %d signals generated %s", len(signals), by_type)
    out.write_dataframe(to_spark(ctx, signals, SCHEMA))
