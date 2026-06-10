"""Ontology object-type backing datasets.

One transform per object type, shaped exactly as Ontology Manager expects
(stable primary key, one row per object, arrays for multi-valued
properties). docs/02_ONTOLOGY_SETUP.md maps each dataset to its object
type, properties, and link types.
"""
from __future__ import annotations

import logging

import pandas as pd
from transforms.api import Input, Output, transform

from stratum import config
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)


@transform(
    out=Output(config.ontology("ontology_country")),
    countries=Input(config.reference("ref_country_iso_lookup")),
    profiles=Input(config.scores("score_country_threat_profiles")),
    budget=Input(config.features("feature_budget_discrepancy")),
)
def country(ctx, out, countries, profiles, budget):
    """Country object — every target country, even without active signals."""
    ref = countries.dataframe().toPandas()
    ref = ref[ref["iso3"].isin(config.TARGET_COUNTRIES)]
    prof = profiles.dataframe().toPandas()
    bud = budget.dataframe().toPandas()
    latest_bud = (bud.sort_values("year").groupby("country_code").tail(1)
                  if len(bud) else bud)

    df = ref.rename(columns={"iso3": "country_code"})[
        ["country_code", "country_name", "region", "is_nato", "is_monitored"]]
    df = df.merge(prof, on="country_code", how="left")
    df = df.merge(
        latest_bud[["country_code", "sipri_milex_usd", "wb_milex_usd_implied",
                    "sipri_milex_pct_gdp", "gdp_usd", "gdp_growth_pct",
                    "population", "budget_credibility_flag"]],
        on="country_code", how="left",
    )
    df = df.rename(columns={
        "sipri_milex_usd": "declared_defense_budget_usd",
        "wb_milex_usd_implied": "worldbank_milex_usd",
        "sipri_milex_pct_gdp": "defense_pct_gdp",
        "budget_credibility_flag": "budget_discrepancy_flag",
    })
    df["composite_threat_tier"] = df["composite_threat_tier"].fillna("C")
    df["threat_acceleration_index"] = df["threat_acceleration_index"].fillna(0.0)
    df["active_conflict"] = df["active_conflict"].fillna(False)
    out.write_dataframe(to_spark(ctx, df))


@transform(
    out=Output(config.ontology("ontology_procurement_contract")),
    classified=Input(config.features("feature_contracts_llm_classified")),
)
def procurement_contract(ctx, out, classified):
    df = classified.dataframe()
    out.write_dataframe(df)


@transform(
    out=Output(config.ontology("ontology_company")),
    companies=Input(config.features("feature_companies")),
)
def company(ctx, out, companies):
    out.write_dataframe(companies.dataframe())


@transform(
    out=Output(config.ontology("ontology_commodity_flow")),
    flows=Input(config.features("feature_comtrade_with_baselines")),
)
def commodity_flow(ctx, out, flows):
    pdf = flows.dataframe().toPandas()
    pdf = pdf.rename(columns={"reporter_country": "country_code",
                              "commodity_name": "commodity_name"})
    out.write_dataframe(to_spark(ctx, pdf))


@transform(
    out=Output(config.ontology("ontology_threat_signal")),
    signals=Input(config.scores("threat_signals")),
)
def threat_signal(ctx, out, signals):
    out.write_dataframe(signals.dataframe())


@transform(
    out=Output(config.ontology("ontology_arms_transfer")),
    transfers=Input(config.clean("clean_sipri_arms_transfers")),
)
def arms_transfer(ctx, out, transfers):
    out.write_dataframe(transfers.dataframe())


@transform(
    out=Output(config.ontology("ontology_conflict_event")),
    acled=Input(config.clean("clean_acled_events")),
)
def conflict_event(ctx, out, acled):
    pdf = acled.dataframe().toPandas()
    pdf["event_source"] = "acled"
    pdf["actors_involved"] = pdf[["actor1", "actor2"]].apply(
        lambda r: [a for a in r if isinstance(a, str) and a], axis=1)
    out.write_dataframe(to_spark(ctx, pdf))
