# STRATUM — Foundry Runbook (start here)

This is the click-by-click path from an empty Foundry enrollment to the full
STRATUM pipeline running. Follow the steps in order; each later doc dives
deeper into one subsystem.

> Foundry's UI evolves and labels occasionally drift between enrollments.
> Where something might differ on your stack, the step says what to look for
> instead of an exact label.

---

## 0. What you need before starting

- Foundry access with permission to create a Project, Code Repository,
  Data Connection sources, and Ontology entities (Build Challenge
  enrollments have all of this).
- The three manual downloads + three registrations from
  [01_DATA_ACQUISITION.md](01_DATA_ACQUISITION.md). You can defer all of
  them: `scripts/make_sample_raw_data.py` generates sample files that
  exercise the entire pipeline first.

### Notes for AIP Developer-tier accounts

There is **no migration** to do — this repo was written *for* Foundry; you
are loading it, not porting it. On first login to your developer
enrollment, take five minutes to check what's enabled (it determines which
path you take at each fork in this runbook):

1. **Apps visible?** Confirm you can open: Compass (files), Data
   Connection, Code Repositories, Pipeline Builder, Ontology Manager,
   Workshop, AIP Logic. Dev tiers generally include all of these.
2. **AIP models:** open AIP / model catalog and note which LLMs are listed
   (GPT-4o / Claude / etc.) and copy a model RID → `config.AIP_MODEL_RID`.
   If the list is empty, run with `LLM_MODE = "keyword"` until model
   access is enabled.
3. **Egress:** try creating one REST API source in Data Connection (start
   with `api.usaspending.gov`). If creating a network egress policy needs
   an approval you don't have, don't fight it — use the
   `scripts/local_fetch.py` upload path (§4b) for everything. The
   pipeline is identical either way; ingestion provenance is the only
   difference.
4. **Resource limits:** developer tiers cap compute and storage. Our
   defaults are already sized for this (DoD-only USASpending agencies,
   2020+ scope, world-total Comtrade rows, GDELT pre-aggregated in
   BigQuery before it ever reaches Foundry).

## 1. Create the project skeleton

1. In Foundry, create a Project named **STRATUM**.
2. Inside it create folders (New > Folder):
   ```
   STRATUM/
     data/raw        data/clean      data/features
     data/scores     data/reference  data/ontology
     pipeline/       (the code repository will live here)
     applications/   (Workshop app, AIP Logic functions)
   ```
3. Open `transforms-python/src/stratum/config.py` in this repo and set
   `PROJECT_ROOT` to your project's path (copy it from the address bar /
   Compass breadcrumb, e.g. `/Acme Org/STRATUM`). Every dataset path in the
   pipeline derives from this one constant.

## 2. Upload the reference datasets

For each CSV in `reference-data/`:

1. Go to `STRATUM/data/reference` > **New > Dataset** > **Import** >
   upload the file as a **tabular CSV** (accept the inferred schema).
2. Name the dataset exactly like the file (without `.csv`):
   - `ref_country_iso_lookup`
   - `ref_hs_capability_mapping`
   - `ref_naics_domain_mapping`
   - `ref_cameo_event_codes`

## 3. Create the raw datasets (manual-upload sources)

In `STRATUM/data/raw`, create datasets by uploading files:

| Dataset | File | Upload mode |
|---|---|---|
| `raw_sipri_milex` | SIPRI milex workbook (.xlsx) | **keep as files** (no schema) |
| `raw_sipri_arms_transfers` | SIPRI trade-register export (.csv) | **keep as files** |
| `raw_opensanctions_entities` | `targets.simple.csv` | tabular CSV |
| `raw_gdelt_events` | BigQuery aggregation CSV (see 01 doc) | tabular CSV |

For "keep as files": in the import dialog choose the option that imports
raw files without applying a schema (the parsing transforms read the bytes
directly, so banner rows in SIPRI files don't matter).

The API-fed datasets (`raw_usaspending_contracts`, `raw_dod_contracts_daily`,
`raw_comtrade_flows`, `raw_worldbank_indicators`, `raw_acled_events`) are
**created automatically by their ingest transforms** on first build — you
don't create them by hand. (If you use the local-fetch path instead of
External Transforms — see step 4b — create them as tabular CSV uploads of
the files in `local-data/`.)

## 4. API connectivity — pick ONE path (or mix per source)

### 4a. External Transforms (platform-native, what the judges like)

For each API system create a **Data Connection source**:

1. **Data Connection** app > **New Source** > choose **REST API**.
2. Connect via **direct connection** (these are public internet APIs).
3. Set the base URL:
   - `https://api.usaspending.gov`
   - `https://www.defense.gov`
   - `https://comtradeapi.un.org`
   - `https://api.worldbank.org`
   - `https://acleddata.com` (new OAuth API) or `https://api.acleddata.com` (legacy key)
   - `https://data.opensanctions.org`
4. Under the source's networking/egress section, add (or attach an existing)
   **network egress policy** for that domain. If your enrollment requires an
   admin to approve egress policies, request them early — it's the only
   approval gate in this whole build.
5. For Comtrade and ACLED, add the credentials as **additional secrets** on
   the source, named to match `stratum/sources.py`:
   - Comtrade: `ComtradeApiKey`
   - ACLED: `AcledApiKey` + `AcledEmail` (legacy) or `AcledToken` (OAuth)
   (If your version prefixes additional secrets, e.g.
   `additionalSecretComtradeApiKey`, update the constant in
   `stratum/sources.py` to the exact name shown.)
6. Enable **"Allow this source to be imported into code repositories"**
   (a.k.a. code-import / external-transforms toggle on the source).
7. Copy each **Source RID** and paste it into
   `transforms-python/src/stratum/sources.py`.

### 4b. Local fetch + upload (zero approvals, fastest to demo)

On your laptop: `python scripts/local_fetch.py <source>` for each of
usaspending / worldbank / comtrade / acled / gdelt / opensanctions / dod,
then upload each CSV from `local-data/` into the matching `raw_*` dataset.
Delete (or just never build) the `stratum/datasets/ingest/*` transforms and
the pipeline runs identically from the uploaded raw data.

Mixing is fine: e.g. External Transforms for the keyless APIs
(USASpending, World Bank), local fetch for Comtrade/ACLED/GDELT.

## 5. Create the code repository and load the pipeline

1. In `STRATUM/pipeline` > **New > Code repository** > type **Python
   transforms** (Transforms language: Python). Name it `stratum-pipeline`.
2. Get this code into it — two options:
   - **Work locally (recommended):** the repo's "Work locally" / clone
     dialog gives you a git URL + token. Clone it, then copy this repo's
     `transforms-python/src/stratum` and `transforms-python/src/test`
     over the bootstrapped `src/` content, replace `src/setup.py` and
     `src/setup.cfg`, and merge the `requirements/run` list from
     `transforms-python/conda_recipe/meta.yaml` into the bootstrapped
     `conda_recipe/meta.yaml`. Commit and push.
   - **In-browser:** recreate the files through the repo editor (tedious
     but works where local git is blocked).
3. In the repo's **Libraries** panel add (this edits meta.yaml for you):
   `requests`, `beautifulsoup4`, `openpyxl`, `pandas`,
   `transforms-external-systems`, and `palantir_models` (only if
   LLM_MODE="aip").
4. If you set up sources (4a): use the repo's **External systems / Sources**
   side panel to import each source into the repo — this authorizes the
   `Source(...)` RIDs you pasted.
5. Decide the LLM mode in `stratum/config.py` (see
   [03_AIP_SETUP.md](03_AIP_SETUP.md)): `"aip"` (default), `"keyword"`
   (no model needed — start here if AIP isn't enabled yet), or
   `"external"`.
6. Commit. **Checks** must go green — they run the same pytest suite you
   can run locally (`cd transforms-python/src && python -m pytest test`).

## 6. First build

Build order (Dataset Preview > Build, or from the repo's build button —
downstream of the raw data you have):

1. Ingest transforms (if using External Transforms) — note Comtrade only
   processes ~450 (reporter, year) pairs per run; schedule it daily and let
   the queue drain over a few days.
2. `clean_*` datasets.
3. `feature_*` (the LLM classification transform classifies up to
   `LLM_MAX_CONTRACTS_PER_RUN` per build and caches — rebuild it until the
   backlog clears).
4. `score_*`, `threat_signals`, `score_country_threat_profiles`.
5. `ontology_*` export datasets.

The repo's **Data Lineage** view (open any output dataset > lineage) now
shows the full DAG — raw -> clean -> features -> scores -> ontology. This
is one of the demo money-shots; keep it tidy.

## 7. Ontology, AIP, Workshop, schedules

- Object types + links + Actions: [02_ONTOLOGY_SETUP.md](02_ONTOLOGY_SETUP.md)
- AIP Logic report generation + AIP Agent: [03_AIP_SETUP.md](03_AIP_SETUP.md)
- Workshop application (7 pages): [04_WORKSHOP_BUILD_GUIDE.md](04_WORKSHOP_BUILD_GUIDE.md)
- Schedules + health checks: [05_SCHEDULES_AND_HEALTH.md](05_SCHEDULES_AND_HEALTH.md)

## 8. Demo-day checklist (success criteria from the build prompt)

1. Open a contract in Workshop → show its LLM classification → the
   ThreatSignal it supports → the country tier it moved. (Full pipeline,
   end to end.)
2. Country Deep-Dive radar: declared-vs-material polygon gap for IRN (the
   sample scenario plants this; real data usually shows it too).
3. Show the compound signal and step through its supporting evidence links.
4. Click **Generate Intelligence Report** on a signal → AIP Logic returns a
   structured report in seconds.
5. Walk the lineage graph to show pipeline craftsmanship.
