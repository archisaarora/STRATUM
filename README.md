# STRATUM

**Geopolitical Threat Capability Intelligence Platform** — built natively on
Palantir Foundry (Transforms + Ontology + AIP + Workshop) for the Palantir
Build Challenge.

STRATUM detects, scores, and forecasts state-level capability development
from entirely open sources, across three intelligence layers:

1. **Procurement Language Intelligence** — LLM classification of government
   contract text into an 18-domain capability taxonomy (hypersonics →
   biodefense), with technology keywords, threat relevance, and maturity
   stage.
2. **Material Credibility Scoring** — declared defense budgets (SIPRI,
   World Bank) cross-referenced against physical commodity flows
   (UN Comtrade defense-relevant HS codes) and arms transfers; 3-year
   rolling baselines flag countries whose imports run ahead of (or behind)
   what they declare.
3. **Anomaly Detection & Threat Scoring** — a rule engine emits discrete
   ThreatSignals (material anomalies, procurement accelerations, budget
   discrepancies, arms-transfer spikes), escalates **compound signals**
   when independent indicators converge, and rolls everything into per-
   country threat tiers (S/A/B/C) with lead-time estimates.

The output is decision support — signals with evidence chains and
AIP-generated intelligence reports — not charts.

## Repository layout

```
transforms-python/        -> contents for your Foundry Code Repository
  conda_recipe/meta.yaml     dependencies (merge into the bootstrapped file)
  src/stratum/
    config.py                ONE place for paths, countries, HS codes, thresholds
    sources.py               Data Connection Source RIDs (paste yours here)
    core/                    pure pandas logic — runs locally AND in Foundry
      clients/               USASpending, defense.gov, Comtrade, World Bank,
                             ACLED, OpenSanctions, GDELT-BigQuery
      parsing/               SIPRI milex xlsx, SIPRI arms CSV, OpenSanctions
      features/              baselines, budget discrepancy, arms velocity,
                             conflict intensity, contract merge/companies
      llm/                   taxonomy, prompt, keyword classifier, JSON guard
      scoring/               credibility, acceleration, signal engine, profiles
      report.py              intelligence report skeleton
      sample_data.py         synthetic demo scenario (compound signal planted)
    datasets/                Foundry transform wrappers (ingest/clean/features/
                             scores/ontology_export)
  src/test/                  30 pytest tests incl. full-pipeline integration —
                             run locally and in Foundry CI checks
reference-data/           -> upload as Foundry datasets (ref_*)
scripts/
  local_fetch.py             pull APIs from your laptop -> CSVs to upload
  make_sample_raw_data.py    write the synthetic scenario as uploadable files
  gen_country_reference.py   regenerate the country lookup (dev-time)
model-training/           -> Mistral-7B QLoRA fine-tune (Stage 5, runs on GPU)
docs/                     -> the Foundry runbook (start at 00)
```

## Quick start

1. **Read [docs/00_FOUNDRY_RUNBOOK.md](docs/00_FOUNDRY_RUNBOOK.md)** — the
   ordered click-by-click path (project → uploads → sources → code repo →
   builds → ontology → Workshop).
2. Data acquisition (downloads + registrations):
   [docs/01_DATA_ACQUISITION.md](docs/01_DATA_ACQUISITION.md).
3. No data yet? `python scripts/make_sample_raw_data.py` generates sample
   files for every raw dataset with a planted storyline (IRN compound
   signal, USA hypersonics acceleration, MMR arms spike) so you can build
   and demo the entire pipeline today.

## Run it locally (no Foundry needed)

The full pipeline runs on your machine against whatever files you have —
use it to validate downloads before uploading them to Foundry and to see
signals/profiles/reports immediately:

```bash
pip install pandas pyarrow requests beautifulsoup4 openpyxl pytest

# instant demo on the synthetic scenario (compound signal, report, profiles)
python scripts/run_local_pipeline.py --sample

# real data: drop files into local-data/ (SIPRI xlsx, local_fetch outputs…)
python scripts/local_fetch.py worldbank
python scripts/local_fetch.py usaspending
python scripts/local_fetch.py comtrade --monitored-only   # works without a key
python scripts/run_local_pipeline.py
# -> local-data/outputs/: threat_signals.csv, country_threat_profiles.csv,
#    intel_report_<top-country>.md, plus every intermediate dataset as CSV
```

Missing sources are skipped gracefully (see docs/01, "Running without
ACLED / GDELT / SIPRI arms"). Test suite (same one Foundry CI runs):

```bash
cd transforms-python/src && python -m pytest test
```

## Pipeline at a glance

```
raw_usaspending_contracts ┐
raw_dod_contracts_daily   ├─ clean_* ── feature_contracts_merged ── [LLM 3.1] ── feature_contracts_llm_classified ─┐
                          │                                                                                        ├─ score_procurement_acceleration ┐
raw_comtrade_flows ─ clean_comtrade_flows ─ capability_mapped ─ feature_comtrade_with_baselines ─┐                 │                                  │
raw_sipri_milex ──── clean_sipri_milex ──────────────┐                                           ├─ score_material_credibility ────────────────────── ├─ threat_signals ── score_country_threat_profiles ── ontology_*
raw_worldbank ────── clean_worldbank_indicators ─────┴─ feature_budget_discrepancy ──────────────┤                                                    │
raw_sipri_arms ───── clean_sipri_arms_transfers ─ feature_arms_transfer_velocity ────────────────┤                                                    │
raw_gdelt_events ─── clean_gdelt_country_daily ──┐                                               │                                                    │
raw_acled_events ─── clean_acled_events ─────────┴─ feature_conflict_intensity_monthly ──────────┘────────────────────────────────────────────────────┘
raw_opensanctions ── clean_opensanctions ─ feature_companies (sanctions cross-reference)
```

Signal rules (Stage 4.3): material anomaly (>0.7 score AND >100% over
baseline), procurement acceleration (12-mo count >2x prior AND value
growth >50%), budget discrepancy (SIPRI vs World Bank >15%, or
under-declaration score >60), arms-transfer spike (>2x rolling average),
and **compound** (≥2 distinct types converging on a country-domain within
6 months → geometric mean × 1.5).

## The LLM layer

- Default: AIP model inside the classification transform
  (`config.LLM_MODE = "aip"`), strict-JSON prompt + validation + retries +
  keyword fallback, permanent per-contract cache.
- `"keyword"` mode runs the whole platform with zero LLM dependency.
- `"external"` mode targets the fine-tuned Mistral-7B-Instruct
  (QLoRA, 4-bit) from `model-training/` — deployment gate F1 > 0.78.

See [docs/03_AIP_SETUP.md](docs/03_AIP_SETUP.md), including the AIP Logic
"Generate Intelligence Report" function and the bonus AIP Agent.

## Data sources

| Source | Access | Ingest path |
|---|---|---|
| USASpending.gov | free API, no key | External Transform (or local fetch) |
| defense.gov contracts | scrape | External Transform (or local fetch) |
| SIPRI Milex | manual xlsx download | upload → parsing transform |
| SIPRI Arms Transfers | manual CSV export | upload → parsing transform |
| UN Comtrade | free API key (500/day) | rate-limited queue transform |
| World Bank | free API, no key | snapshot transform |
| GDELT 2.0 | BigQuery free tier | aggregate SQL → CSV upload / BQ source |
| ACLED | free key/token | incremental transform |
| OpenSanctions | free bulk CSV | External Transform or upload |

All figures in `sample-data/` are synthetic. STRATUM processes only
publicly available data.
