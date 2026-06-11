# STRATUM Tech Stack

What every technology in the repo is, and why it was chosen.

## Languages & runtime

| Tech | Where | Why |
|---|---|---|
| **Python 3.10+** | everything | One language end-to-end: ingestion, analytics, dashboard, and Foundry transforms are all Python, so the same business logic runs locally and in the cloud without porting. |
| **pandas + NumPy** | `stratum/core/*` | All analytics (rolling baselines, z-scores, percentile ranks, signal rules) are vectorized DataFrame operations — testable, deterministic, fast at this data scale (10⁴–10⁶ rows). |
| **PySpark** | 2 Foundry transforms | Only where data can genuinely get big (USASpending cleaning, GDELT aggregation). Everything else stays pandas for simplicity. |

## Data acquisition

| Tech | Where | Why |
|---|---|---|
| **requests** | `core/clients/*` | Plain HTTPS calls to the seven source APIs, wrapped in one shared exponential-backoff retry (`core/http.py`, 2/4/8/16s + jitter, honors Retry-After). |
| **BeautifulSoup4** | `core/clients/dod.py` | Parses defense.gov contract-announcement HTML into structured records. `html.parser` backend — no lxml dependency. |
| **openpyxl** | `core/parsing/*` | Reads the SIPRI Excel workbooks (and writes the synthetic sample workbook). |
| **google-cloud-bigquery** *(optional)* | `core/clients/gdelt_bq.py` | GDELT raw is terabytes; the public BigQuery mirror lets us pull pre-aggregated country-day rows for pennies of free-tier quota. |

## Storage & state

| Tech | Where | Why |
|---|---|---|
| **CSV files** | `local-data/outputs/`, `sample-data/outputs/` | The local pipeline's interchange format. Human-inspectable, diff-able, drag-and-drop uploadable to Foundry. Each file name == a Foundry dataset name. |
| **JSON checkpoint files** | `local-data/*.json` | Resumable work queues for rate-limited APIs (Comtrade: 450 calls/day budget). |
| **analyst_state.json** | next to outputs | Signal review state (reviewed/escalated/notes), keyed by **deterministic signal IDs** (SHA-1 of type+country+domain+window) so analyst work survives pipeline re-runs. |
| **UTF-8 everywhere** | all text I/O | Explicit `encoding="utf-8"` on every read/write — Windows otherwise defaults to cp1252 and crashes on report typography. |

## Analytics & detection (no ML magic — auditable statistics)

| Technique | Where | What it catches |
|---|---|---|
| 3-year trailing rolling baseline + deviation % + z-score blend | `core/features/baselines.py` | Commodity imports far above a country's own norm. |
| Cross-country percentile ranks per (domain, year) | `core/scoring/material_credibility.py` | Countries whose *physical* standing outranks their *declared* standing. |
| Import-intensity ratio + peer z-score + dual-use/direct stream split | `core/features/import_intensity.py` | The covert pattern: precursor imports surging while visible weapons imports stay flat. |
| 12-month windowed growth comparisons | `core/scoring/procurement_acceleration.py`, `arms_velocity.py` | Contract and arms-transfer tempo spikes. |
| Rule engine + geometric-mean compounding (×1.5 escalation) | `core/scoring/signals.py` | Independent indicators converging on the same country+domain. |
| Keyword/NAICS classifier (regex banks per 18-domain taxonomy) | `core/llm/keyword_classifier.py` | Deterministic contract classification — the no-LLM fallback and the weak-label generator for fine-tuning. |

## LLM layer (three interchangeable modes)

| Mode | Tech | When |
|---|---|---|
| `aip` | **palantir_models** (GPT/Claude via Foundry AIP) | Production on Foundry — strict-JSON prompt, validation + 3 retries at temp 0, keyword fallback, permanent per-contract cache. |
| `keyword` | regex banks | Local runs and before AIP access — zero dependencies. |
| `external` | **Mistral-7B-Instruct + QLoRA** (transformers/peft/trl/bitsandbytes), served via **llama-cpp-python** | The fine-tuned model path (`model-training/`); deployment gated on F1 > 0.78. |

## Dashboard

| Tech | Why |
|---|---|
| **Streamlit** | Whole UI in Python; one command to serve (`streamlit run app/STRATUM.py`); pages = files; built-in widgets cover tables/metrics/forms. |
| **Plotly** | Every chart is interactive (hover, zoom, click). Selection events (`on_select="rerun"`) power the click-a-country → deep-dive and click-a-cell → filter-feed flows. Choropleth world map needs no tile server or API key. |
| **streamlit.testing AppTest** | Headless render test of every page (`scripts/smoke_test_app.py`) — CI-able without a browser. |

## Testing & quality

| Tech | What's covered |
|---|---|
| **pytest** (46 tests) | Parsers against real-file quirks (SIPRI %GDP fractions, TIV parentheses), every feature/scoring function, mocked-session API contract tests (Comtrade public preview, Data360), empty/skipped-source paths, and a full-pipeline integration test that asserts the planted demo storyline (compound signal fires, calm countries stay quiet). |
| Deterministic IDs (`stable_id`) | Idempotent re-runs: no duplicate signals/contracts/flows; ontology writebacks and analyst state survive rebuilds. |

## Palantir Foundry deployment (same code, bigger engine)

| Foundry piece | Role |
|---|---|
| **Code Repositories (transforms-python)** | `stratum/datasets/*` wraps the same `stratum/core` functions as `@transform`s; CI runs the same pytest suite. |
| **External Transforms (Data Connection sources)** | Governed egress + secrets for the API ingests, with incremental checkpointing. |
| **AIP** | LLM classification in-pipeline (`palantir_models`) + AIP Logic for report generation + optional Agent. |
| **Ontology / Workshop** | Objects (Country, ThreatSignal, …) with Actions for analyst writebacks; the operational UI (docs/02 & 04). |
