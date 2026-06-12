# STRATUM — Geopolitical Threat Capability Intelligence

STRATUM watches what states **do**, not what they **say**. It cross-references
every country's *declared* military posture (budgets, announced programs)
against *physical evidence* (commodity imports, arms transfers, procurement
contracts) — all from open sources — and raises structured threat signals
when the two stories diverge.

**The core insight:** a state building capability covertly rarely imports
finished weapons; those are visible and embargoed. It imports *precursors* —
propellant chemicals, titanium, ferroalloys, guidance electronics — that look
like ordinary industrial trade. One import line is noise. The same country's
propellant imports tripling **while** its declared budget stays flat **and**
its direct weapons imports don't move **and** its budget disagrees with
independent compilations — that convergence is a signal, and it's exactly
what a human analyst scanning one database at a time would miss.

## What it produces

| Output | Meaning |
|---|---|
| **ThreatSignal** | A discrete, evidence-linked alert. Types: `material_anomaly` (commodity import >100% over its 3-yr baseline), `covert_acquisition` (dual-use imports surge while direct military imports + budget stay flat), `budget_discrepancy` (SIPRI vs World Bank figures diverge >15%, or imports outrank declared spend vs peers), `procurement_acceleration` (12-mo contract count >2× prior AND value +50%), `arms_transfer_spike` (deliveries >2× rolling avg), `compound_signal` (≥2 independent types converge on one country+domain in 6 months → escalated). |
| **Country threat profile** | Threat Acceleration Index (0–100) → tier S/A/B/C, top domains of concern, material-credibility score, lead-time estimate to operational capability (from contract maturity stages). |
| **Intelligence report** | A structured assessment (Executive Summary → Recommended Action) rendered in the dashboard and exportable as markdown. |

Everything is inspectable: every signal carries the IDs of the flows,
contracts, or transfers that triggered it.

## Quick start (standalone — no Foundry, no keys)

Requires Python 3.10+.

```bash
git clone https://github.com/archisaarora/STRATUM.git
cd STRATUM
pip install -r requirements.txt

python scripts/run_local_pipeline.py --sample   # build the demo scenario
streamlit run app/STRATUM.py                    # open http://localhost:8501
```

The demo plants a realistic storyline: Iran's propellant-precursor imports
triple against a flat declared budget → `material_anomaly` +
`covert_acquisition` + `budget_discrepancy` → **compound signal**, tier A.
Click the red country on the map and follow the evidence.

### Real data

| Source | What it provides | Access |
|---|---|---|
| [SIPRI Milex](https://www.sipri.org/databases/milex) | declared military budgets, 1949– | one xlsx download, no signup |
| [UN Comtrade](https://comtradeplus.un.org) | bilateral trade by HS code (31 defense-relevant codes tracked) | **works keyless** via the public preview API; free key = 30× fewer calls |
| [USASpending](https://api.usaspending.gov) | US federal contracts with full descriptions | free API, no key |
| [World Bank](https://api.worldbank.org) | GDP, milex %GDP (independent of SIPRI), population | free API, no key |
| [OpenSanctions](https://opensanctions.org) | consolidated sanctions/watchlists | free bulk CSV, no key |
| [defense.gov](https://www.defense.gov/News/Contracts/) | daily DoD contract announcements | scraped, no key |
| [SIPRI Arms Transfers](https://armstransfers.sipri.org) | major weapons transfers + TIV values | CSV/XLSX export, no signup |
| [UCDP GED](https://ucdp.uu.se/downloads/) | georeferenced conflict events | free CSV, no signup (ACLED alternative) |
| [ACLED](https://acleddata.com) *(optional)* | political violence events | free academic key |
| [GDELT](https://www.gdeltproject.org) *(optional)* | global news event tempo | free via BigQuery |

```bash
# drop your SIPRI xlsx into local-data/, then:
python scripts/local_fetch.py worldbank
python scripts/local_fetch.py usaspending
python scripts/local_fetch.py comtrade --monitored-only   # keyless, resumable
python scripts/run_local_pipeline.py
# switch the dashboard sidebar to "My data (local-data)"
```

Any source can be skipped — the pipeline degrades gracefully
(docs/01_DATA_ACQUISITION.md).

## The dashboard

Six pages, cross-linked (click a country anywhere → its deep dive):

1. **Command Center** — clickable world threat map, tier KPIs with
   run-over-run deltas, filterable signal feed with row expansion,
   click-to-filter domain heat matrix, signal-volume tracking.
2. **Country Deep-Dive** — tier/TAI/credibility/lead-time header; the
   declared-vs-material radar; **Import Forensics** tab: dual-use vs
   direct import streams, per-commodity drill-down with baseline band +
   anomaly markers + unit-price check; arms transfers; conflict context;
   per-signal **live news corroboration** (GDELT, 65 languages, one click);
   in-app intelligence report.
3. **Material Credibility** — credibility leaderboard with import-trend
   sparklines, budget-credibility scatter, **covert-acquisition
   watchlist**, anomalous-flows table.
4. **Procurement Intelligence** — searchable classified contracts, domain
   velocity, contractor table with sanctions matches highlighted.
5. **Signal Tracking** — triage queue (review / escalate / dismiss /
   notes — state survives re-runs), signal timeline.
6. **Data Health** — source freshness, row counts, run history.

## Documentation

| Doc | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | how the code is organized and how data flows raw → signals |
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | every technology used and why |
| [docs/00_FOUNDRY_RUNBOOK.md](docs/00_FOUNDRY_RUNBOOK.md) | deploying the same pipeline on Palantir Foundry (AIP) |
| [docs/01_DATA_ACQUISITION.md](docs/01_DATA_ACQUISITION.md) | per-source acquisition guide, API-novice friendly |
| [docs/02–05](docs/) | Foundry ontology, AIP/LLM setup, Workshop build, schedules |

## Verification

```bash
cd transforms-python/src && python -m pytest test   # 46 tests incl. e2e scenario
cd ../.. && python scripts/smoke_test_app.py        # renders every dashboard page
```

All sample data is synthetic. STRATUM processes only publicly available
data; outputs are OSINT estimates, not classified assessments.
