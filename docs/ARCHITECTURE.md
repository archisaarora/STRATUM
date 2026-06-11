# STRATUM Architecture

How the code is organized, how data flows from raw downloads to threat
signals, and where each computation lives.

## The one rule that organizes everything

**All business logic lives in `transforms-python/src/stratum/core/` as pure
pandas functions.** Nothing in `core` imports Foundry, Streamlit, or any
runtime-specific library. Three thin shells call the same functions:

```
                    ┌──────────────────────────────┐
                    │   stratum/core  (pure pandas) │
                    │  clients · parsing · features │
                    │  llm · scoring · report       │
                    └──────────────────────────────┘
                       ▲             ▲            ▲
        ┌──────────────┘             │            └──────────────┐
┌───────┴────────┐        ┌──────────┴─────────┐       ┌─────────┴────────┐
│ Foundry shells │        │ Local runner       │       │ Dashboard        │
│ stratum/       │        │ scripts/           │       │ app/ (Streamlit) │
│  datasets/*    │        │  run_local_        │       │ reads the        │
│ (@transform    │        │  pipeline.py       │       │ runner's CSV     │
│  wrappers)     │        │ (CSV in → CSV out) │       │ outputs          │
└────────────────┘        └────────────────────┘       └──────────────────┘
```

A fix to a detection rule lands in one file in `core` and every runtime —
Foundry build, local CLI, dashboard — picks it up.

## Data flow (Layer 1/2/3 of the intelligence model)

```
RAW (downloads + API pulls)          CLEAN (standardized)            FEATURES                          SCORES / SIGNALS
───────────────────────────         ─────────────────────           ────────────────────────          ─────────────────────────────
raw_usaspending_contracts ──┐
raw_dod_contracts_daily ────┤→ clean contracts ─→ feature_contracts_merged ─→ [LLM/keyword classify] ─→ score_procurement_acceleration ─┐
                            │                                                                                                           │
raw_comtrade_flows ─────────┼→ clean_comtrade_flows ─→ capability mapping ─→ feature_comtrade_with_baselines ─┬→ score_material_credibility ──┤
raw_sipri_milex (xlsx) ─────┼→ clean_sipri_milex ──────────────────────────────────────────────────────────────┼→ feature_import_intensity ────┤→ threat_signals ─→ score_country_threat_profiles
raw_worldbank_indicators ───┼→ clean_worldbank ─────→ feature_budget_discrepancy ──────────────────────────────┘                              │        │
raw_sipri_arms (csv/xlsx) ──┼→ clean_sipri_arms ────→ feature_arms_transfer_velocity ──────────────────────────────────────────────────────────┤        ▼
raw_acled / raw_gdelt ──────┼→ clean events ────────→ feature_conflict_intensity_monthly ──────────────────────────────────────────(context)──┘   intelligence report
raw_opensanctions ──────────┘→ clean_opensanctions ─→ feature_companies (sanctions cross-reference)
```

Every country name passes through `ref_country_iso_lookup` (249 countries +
aliases for SIPRI/World Bank/Comtrade naming quirks) — never ad-hoc string
matching.

## The three intelligence layers

1. **Procurement language (Layer 1)** — contract descriptions →
   18-domain capability taxonomy + technology keywords + maturity stage
   (research/development/production/sustainment). Maturity stages drive
   the lead-time estimates in country profiles.
2. **Material credibility (Layer 2)** — the "watch what they buy" layer:
   - *Baselines:* each (country, HS code) import series vs its own 3-year
     trailing average; blended deviation/z anomaly score.
   - *Credibility:* cross-country percentile of material evidence vs
     percentile of declared programs, per domain — divergence =
     under/over-declaration.
   - *Import-intensity forensics:* imports split into **direct military**
     (HS 93 arms, 8906 warships, 8802 aircraft) vs **dual-use precursors**
     (propellant chemicals 28xx/36xx, titanium 8108, ferroalloys 7202,
     ICs 8542 …). Ratio to declared budget, z-scored against peers.
3. **Signal generation (Layer 3)** — `core/scoring/signals.py` is a rule
   engine emitting evidence-linked ThreatSignals (six types; see README
   table). Signals of ≥2 distinct types converging on the same
   (country, domain) within 6 months compound at
   `geometric_mean(strengths) × 1.5`. Profiles aggregate active signals
   into the Threat Acceleration Index via a saturating exponential, map
   to tiers (S≥75, A≥50, B≥25), and estimate lead time from contract
   maturity bands.

## Repository map

```
transforms-python/src/stratum/
  config.py                 every threshold, country list, HS code, path
  sources.py                Foundry Data Connection source RIDs + base URLs
  core/
    http.py                 retry/backoff wrapper (all API calls go through it)
    countries.py            CountryIndex — name/code/M49 → ISO3 via reference table
    text.py                 company normalization, money parsing, stable_id
    clients/                usaspending · dod · comtrade (keyed + public) ·
                            worldbank (v2 + Data360) · acled · opensanctions · gdelt_bq
    parsing/                sipri_milex (xlsx) · sipri_arms (register CSV + TIV xlsx) ·
                            opensanctions · ucdp (GED → ACLED shape)
    features/               baselines · budget · arms_velocity · conflict ·
                            contracts · import_intensity
    llm/                    taxonomy · prompts · keyword_classifier · json_guard
    scoring/                material_credibility · procurement_acceleration ·
                            signals (rule engine) · profiles
    report.py               intelligence-report builder
    sample_data.py          synthetic demo scenario (planted compound signal)
  datasets/                 Foundry @transform wrappers (ingest/clean/features/
                            scores/ontology_export) — thin adapters only
test/                       46 pytest tests incl. full-pipeline integration

scripts/
  local_fetch.py            laptop API pulls → uploadable CSVs (keyless paths included)
  run_local_pipeline.py     the local engine: files in → signals/profiles/report out
  convert_ucdp_to_acled.py  UCDP GED → ACLED-shaped events
  make_sample_raw_data.py   write the demo scenario as raw files
  smoke_test_app.py         headless render test of every dashboard page

app/
  loaders.py                cached CSV access, analyst state, cross-page navigation
  STRATUM.py + pages/2–6    the six dashboard pages

reference-data/             ref_country_iso_lookup · ref_hs_capability_mapping ·
                            ref_naics_domain_mapping · ref_cameo_event_codes
model-training/             Mistral-7B QLoRA fine-tune + evaluation gate
sample-data/                demo raw files + placeholders for skipped sources
docs/                       this file · TECH_STACK · Foundry runbook (00–05)
```

## Key design decisions

- **Idempotency by construction.** IDs are content hashes (`stable_id`), so
  re-running anything upserts rather than duplicates — and analyst state
  keyed on those IDs survives every rebuild.
- **Graceful degradation.** Every stage accepts missing inputs (`None` /
  empty frames with stable columns). Skipping ACLED/GDELT/SIPRI-arms costs
  those layers only; Foundry builds stay green via header-only placeholder
  uploads.
- **Two access tiers per hard source.** Comtrade works keyless (public
  preview, 1 code/call, checkpointed queue) or keyed (500 calls/day,
  bulk); World Bank has classic v2 + Data360; ACLED has UCDP as a
  no-registration substitute.
- **Explainability over model magic.** Detection is transparent statistics
  with documented thresholds in `config.py`; the LLM only does text
  classification, and even that has a deterministic fallback. An analyst
  can defend every signal from its evidence list.

## Where to change things

| You want to… | Touch |
|---|---|
| add a tracked commodity | `reference-data/ref_hs_capability_mapping.csv` + `config.DEFENSE_HS_CODES` |
| tune a detection threshold | `stratum/config.py` (all thresholds live there) |
| add a signal rule | `core/scoring/signals.py` (+ weight in `profiles.TYPE_WEIGHTS`) |
| add a data source | client in `core/clients/` → parser/clean step → wire into `run_local_pipeline.py` + a `datasets/` transform |
| add a dashboard view | new file in `app/pages/` (loaders.py gives you cached data + navigation) |
