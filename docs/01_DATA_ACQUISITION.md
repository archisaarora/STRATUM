# Data Acquisition Checklist

Scope decision: **2020 → present**. That yields a 5-year baseline — enough
for 3-year rolling anomaly detection with headroom, without drowning in
data.

## If you're new to APIs — read this first

Every API in this project is a **hosted web service**: you send an HTTPS
request, you get JSON back. You never install anything, never run Docker,
never set up a database.

> ⚠️ **USASpending trap:** the USASpending GitHub repository
> (fedspendingtransparency/usaspending-api) and its Docker/PostgreSQL/
> Elasticsearch instructions are for *hosting your own copy of their
> backend*. **Skip all of it.** The real API is already running at
> `api.usaspending.gov` — free, no key, no signup. Our code calls it
> directly.

The only "setup" any source needs is, at most, an API key — a password
string you paste into a config. The `scripts/local_fetch.py` commands do
every request for you:

```bash
pip install pandas requests beautifulsoup4 openpyxl
python scripts/local_fetch.py usaspending     # no key
python scripts/local_fetch.py worldbank       # no key
python scripts/local_fetch.py dod             # no key
python scripts/local_fetch.py opensanctions   # no key
python scripts/local_fetch.py comtrade        # works WITHOUT a key too (see below)
python scripts/local_fetch.py acled           # needs free registration
python scripts/local_fetch.py gdelt           # needs free Google account
```

Each command writes a CSV into `local-data/` that you upload into the
matching Foundry `raw_*` dataset. That's the whole job.

## One-click downloads (do once, upload to Foundry)

| # | Source | Where | What to grab | Upload to dataset (mode) |
|---|---|---|---|---|
| 1 | SIPRI Military Expenditure | sipri.org/databases/milex | The Excel workbook ("Data for all countries 1949–20xx", ~2 MB). Contains current-US$, constant-US$ and %-GDP sheets. | `raw_sipri_milex` (**files**, no schema) |
| 2 | SIPRI Arms Transfers | armstransfers.sipri.org | Trade Register export: all suppliers, all recipients, order year 1950–present, **CSV** (~5 MB). | `raw_sipri_arms_transfers` (**files**) |
| 3 | OpenSanctions | opensanctions.org/datasets/default → bulk download | `targets.simple.csv` from the consolidated *default* dataset. | `raw_opensanctions_entities` (tabular CSV) — or skip and let the External Transform fetch it |

The parsers tolerate banner rows, '()' TIV values, '...' missing markers and
column-name drift between SIPRI releases. The milex parser is **validated
against the real `SIPRI-Milex-data-1949-2025` workbook** (99.97% country
match; share-of-GDP fractions auto-normalized to percent). If a future
release still breaks parsing, the transform error will name the columns it
saw — extend the regexes in `stratum/core/parsing/`.

### SIPRI Arms Transfers export not working?

The armstransfers.sipri.org exporter is a JavaScript app and is flaky.
In order of preference:

1. Retry in a fresh browser/incognito window: run a query first (all
   suppliers, all recipients, order year 2015–present is plenty), wait for
   the result table to render, *then* use Export/Download → CSV.
2. **Use the TIV tables instead** — on the same site, the "Importer/
   exporter TIV tables" view exports a simple XLSX (recipients × years of
   total TIV). Our pipeline accepts it as-is: drop the `.xlsx` into
   `raw_sipri_arms_transfers` and the clean transform parses it
   (rows marked `tiv_annual`). You lose per-weapon detail but keep
   everything the arms-velocity layer and spike signals need.
3. Worst case, skip the source for now: the pipeline runs without it
   (you just won't get arms_transfer_spike signals) — add it later.

## Free registrations (~5 min each)

| # | Service | Where | You get | Goes where |
|---|---|---|---|---|
| 4 | UN Comtrade *(optional!)* | comtradeplus.un.org → register → subscribe to the free API product | subscription key (500 calls/day, 100K records/call) | `ComtradeApiKey` secret on the Comtrade source (or `COMTRADE_API_KEY` env for local fetch) |
| 5 | ACLED | acleddata.com → register (academic) | API key + registered email, or OAuth token on newer accounts | `AcledApiKey`/`AcledEmail` (or `AcledToken`) secrets on the ACLED source |
| 6 | Google account | console.cloud.google.com | BigQuery free tier (1 TB query/month) for GDELT | used by `scripts/local_fetch.py gdelt` |

### Comtrade without a key — the public preview API

UN Comtrade also exposes a **completely keyless** endpoint:
`https://comtradeapi.un.org/public/v1/preview/C/A/HS`. Limits: one HS code
and one period per call (vs. all-at-once with a key), so the fetch runs as
a slow, resumable queue. `local_fetch.py comtrade` uses it automatically
whenever no key is set:

```bash
# no key: ~8,400 small calls for the full 45-country set, checkpointed —
# run it overnight, or cut ~70% of calls with --monitored-only
python scripts/local_fetch.py comtrade --monitored-only --budget 3000
# re-run until "0 calls pending", then upload local-data/raw_comtrade_flows.csv
```

Get the free subscription key anyway when you can — with it, the same
dataset is ~270 calls instead of ~8,400.

## Zero-setup APIs (no key, no registration)

- **USASpending** — `api.usaspending.gov`, ingest transform pulls contract
  awards (type A–D) with descriptions, monthly windows, DoD by default
  (`config.USASPENDING_AGENCIES` to widen). *(Ignore their GitHub repo's
  Docker setup — that's for self-hosting their backend, not for using
  the API.)*
- **World Bank** — `api.worldbank.org/v2` (classic API, still maintained),
  8 indicators, all countries. The newer **Data360** platform
  (`data360api.worldbank.org`) carries the same WDI series under IDs like
  `WB_WDI_MS_MIL_XPND_GD_ZS`; we support it as a fallback
  (`local_fetch.py worldbank --data360`) in case v2 is ever retired.
- **OpenSanctions** — no key needed for our use: we consume the free bulk
  CSV (`data.opensanctions.org/datasets/latest/default/targets.simple.csv`).
  The `api.opensanctions.org` endpoints you may see documented
  (/search, /match, /reconcile) are a separate keyed service for
  interactive lookups — nice-to-have, not required.

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

## Running without ACLED / GDELT / SIPRI arms (yes, it works)

The signal engine only *requires* SIPRI milex + World Bank + Comtrade +
USASpending — all obtainable with zero registrations. The other three
sources add layers but nothing breaks without them:

| Skipped source | What you lose | What still works |
|---|---|---|
| SIPRI arms transfers | arms_transfer_spike signals, arms panels | all other signal types, compound signals |
| ACLED | conflict-intensity detail, event maps | everything else (conflict is context, not a signal driver) |
| GDELT | news-tempo component of conflict intensity | everything else |

**How to skip a source in Foundry:** the transforms still expect their raw
datasets to exist, so upload the matching **header-only placeholder** from
`sample-data/placeholders/` into the raw dataset instead of real data
(`raw_acled_events.csv`, `raw_gdelt_events.csv`,
`raw_sipri_arms_transfers.csv`). Every downstream transform then produces
a valid empty output — builds stay green, signals come from the sources
you do have. Swap in real data later by appending it to the same dataset;
nothing else changes.

**Free ACLED substitute — UCDP (no registration at all):**

```bash
# 1. download the UCDP Georeferenced Event Dataset from ucdp.uu.se/downloads
#    (one CSV/zip, no account needed)
python scripts/convert_ucdp_to_acled.py ~/Downloads/GEDEvent_v25_1.csv.zip
# 2. upload local-data/raw_acled_events.csv into the raw_acled_events dataset
```

UCDP covers organized violence (battles, one-sided violence) with fatality
estimates — slightly narrower and slower-updating than ACLED, but it
feeds the same conflict-intensity layer unchanged.

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
