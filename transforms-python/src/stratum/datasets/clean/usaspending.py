"""Transform 1.1b — raw -> clean_usaspending_contracts (PySpark).

Kept in Spark: this is the one dataset that can reach millions of rows.
Dedupes on award_id, drops rows without a usable description, casts types,
and maps recipient country codes to ISO3 via a broadcast of the reference
table (codes + uppercased names).
"""
from __future__ import annotations

from pyspark.sql import functions as F
from transforms.api import Input, Output, transform_df

from stratum import config


@transform_df(
    Output(config.clean("clean_usaspending_contracts")),
    raw=Input(config.raw("raw_usaspending_contracts")),
    countries=Input(config.reference("ref_country_iso_lookup")),
)
def compute(raw, countries):
    # Country mapping: ISO3 | ISO2 | uppercased display name | aliases -> ISO3
    iso3 = countries.select(F.col("iso3").alias("ckey"), F.col("iso3").alias("ciso3"))
    iso2 = countries.select(F.col("iso2").alias("ckey"), F.col("iso3").alias("ciso3"))
    names = countries.select(
        F.upper(F.col("country_name")).alias("ckey"), F.col("iso3").alias("ciso3"))
    aliases = (
        countries
        .select(F.explode(F.split(F.coalesce(F.col("aliases"), F.lit("")), r"\|"))
                .alias("alias"), F.col("iso3").alias("ciso3"))
        .where(F.length("alias") > 0)
        .select(F.upper(F.col("alias")).alias("ckey"), "ciso3")
    )
    cmap = iso3.unionByName(iso2).unionByName(names).unionByName(aliases) \
               .dropDuplicates(["ckey"])

    df = (
        raw
        .where(F.col("award_id").isNotNull())
        .where(F.col("award_description").isNotNull()
               & (F.length("award_description") > 20))
        .withColumn("total_obligated_amount",
                    F.col("total_obligated_amount").cast("double"))
        .withColumn("period_of_performance_start_date",
                    F.to_date("period_of_performance_start_date"))
        .withColumn("period_of_performance_current_end_date",
                    F.to_date("period_of_performance_current_end_date"))
        .withColumn("_ckey", F.upper(F.trim(F.coalesce(
            F.col("recipient_country_code"), F.lit("USA")))))
        .dropDuplicates(["award_id"])
    )
    df = (
        df.join(F.broadcast(cmap), df["_ckey"] == cmap["ckey"], "left")
        .withColumn("recipient_country", F.coalesce(F.col("ciso3"), F.lit("USA")))
        .drop("ckey", "ciso3", "_ckey")
    )
    return df.select(
        "award_id", "display_award_id", "recipient_name", "recipient_country",
        "awarding_agency_name", "awarding_sub_agency", "funding_agency_name",
        "award_description", "total_obligated_amount",
        "period_of_performance_start_date",
        "period_of_performance_current_end_date",
        "naics_code", "product_or_service_code", "pop_country_code",
    )
