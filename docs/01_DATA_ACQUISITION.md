# Data Acquisition Checklist

Scope decision: **2020 → present**. That yields a 5-year baseline — enough
for 3-year rolling anomaly detection with headroom, without drowning in
data.

## One-click downloads (do once, upload to Foundry)

| # | Source | Where | What to grab | Upload to dataset (mode) |
|---|---|---|---|---|
| 1 | SIPRI Military Expenditure | sipri.org/databases/milex | The Excel workbook ("Data for all countries 1949–20xx", ~2 MB). Contains current-US$, constant-US$ and %-GDP sheets. | `raw_sipri_milex` (**files**, no schema) |
| 2 | SIPRI Arms Transfers | armstransfers.sipri.org | Trade Register export: all suppliers, all recipients, order year 1950–present, **CSV** (~5 MB). | `raw_sipri_arms_transfers` (**files**) |
| 3 | OpenSanctions | opensanctions.org/datasets/default → bulk download | `targets.simple.csv` from the consolidated *default* dataset. | `raw_opensanctions_entities` (tabular CSV) — or skip and let the External Transform fetch it |

The parsers tolerate banner rows, '()' TIV values, '...' missing markers and
column-name drift between SIPRI releases. If a future release still breaks
parsing, the transform error will name the columns it saw — extend the
regexes in `stratum/core/parsing/`.

## Free registrations (~5 min each)

| # | Service | Where | You get | Goes where |
|---|---|---|---|---|
| 4 | UN Comtrade | comtradeplus.un.org → register → subscribe to the free API product | subscription key (500 calls/day) | `ComtradeApiKey` secret on the Comtrade source (or `COMTRADE_API_KEY` env for local fetch) |
| 5 | ACLED | acleddata.com → register (academic) | API key + registered email, or OAuth token on newer accounts | `AcledApiKey`/`AcledEmail` (or `AcledToken`) secrets on the ACLED source |
| 6 | Google account | console.cloud.google.com | BigQuery free tier (1 TB query/month) for GDELT | used by `scripts/local_fetch.py gdelt` |

## Zero-setup APIs (no key, no registration)

- **USASpending** — `api.usaspending.gov`, ingest transform pulls contract
  awards (type A–D) with descriptions, monthly windows, DoD by default
  (`config.USASPENDING_AGENCIES` to widen).
- **World Bank** — `api.worldbank.org/v2`, 8 indicators, all countries.

## GDELT — the right way

Do **not** download raw GDELT (a single year of GKG is ~2.5 TB). Query the
public BigQuery mirror and keep only country-day aggregates:

```bash
pip install google-cloud-bigquery db-dtypes
gcloud auth application-default login
python scripts/local_fetch.py gdelt        # runs the aggregation SQL
# -> local-data/raw_gdelt_events.csv  (a few MB), upload to raw_gdelt_events
```

The SQL lives in `stratum/core/clients/gdelt_bq.py` (events 2020+, CAMEO
roots 09–20, grouped by day x Actor1CountryCode x root code). Refresh
monthly by re-running and re-uploading — or, platform-native, create a
Data Connection **BigQuery** source pointed at `gdelt-bq.gdeltv2.events`
with the same query as a sync.

## Where everything lands

```
raw_usaspending_contracts   API (External Transform or local fetch)
raw_dod_contracts_daily     scraper (External Transform or local fetch)
raw_sipri_milex             manual upload (xlsx, as files)
raw_sipri_arms_transfers    manual upload (csv, as files)
raw_comtrade_flows          API w/ key (queue, 450 calls/day)
raw_worldbank_indicators    API (snapshot refresh)
raw_gdelt_events            BigQuery aggregate (CSV upload or BQ source)
raw_acled_events            API w/ key (incremental by event date)
raw_opensanctions_entities  bulk CSV (upload or External Transform)
```

Reporting lag to expect: Comtrade ~2 months; SIPRI annual (spring release);
ACLED weekly; GDELT 15 minutes; USASpending daily.
