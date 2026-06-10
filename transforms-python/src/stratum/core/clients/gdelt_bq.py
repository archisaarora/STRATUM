"""GDELT 2.0 via Google BigQuery (the sane way — raw GDELT is terabytes).

Used by scripts/local_fetch.py on a machine with Google credentials
(`gcloud auth application-default login`, free tier), producing a small
aggregated CSV you upload to `raw_gdelt_events`. Inside Foundry you can
instead set up a Data Connection BigQuery source running the same SQL —
see docs/01_DATA_ACQUISITION.md.

Aggregation: country-day conflict summaries over CAMEO root codes 09–20,
keyed on Actor1CountryCode (CAMEO ISO3-style codes).
"""
from __future__ import annotations

AGGREGATION_SQL = """
SELECT
  SQLDATE                       AS event_date_int,
  Actor1CountryCode             AS actor1_country,
  EventRootCode                 AS event_root_code,
  COUNT(*)                      AS event_count,
  AVG(GoldsteinScale)           AS avg_goldstein,
  SUM(NumMentions)              AS total_mentions,
  SUM(NumSources)               AS total_sources
FROM `gdelt-bq.gdeltv2.events`
WHERE SQLDATE >= @start_date
  AND EventRootCode BETWEEN '09' AND '20'
  AND Actor1CountryCode IS NOT NULL
GROUP BY 1, 2, 3
"""


def fetch_country_daily(start_date_int: int) -> "pandas.DataFrame":  # noqa: F821
    """Run the aggregation on BigQuery. Requires google-cloud-bigquery."""
    from google.cloud import bigquery  # optional dependency, local use only

    client = bigquery.Client()
    job = client.query(
        AGGREGATION_SQL,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "INT64", start_date_int)
            ]
        ),
    )
    return job.result().to_dataframe()
