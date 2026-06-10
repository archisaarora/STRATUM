# Schedules, Health Checks, and Operations

## Build schedules (Foundry Scheduler)

Create schedules from each output dataset (Manage > Schedules > New) or
via the lineage view's schedule editor:

| Schedule | Trigger | Targets |
|---|---|---|
| `stratum-daily-ingest` | time: daily 06:00 UTC | `raw_dod_contracts_daily`, `raw_usaspending_contracts`, `raw_comtrade_flows` (queue drainer), `raw_acled_events` |
| `stratum-weekly-refresh` | time: Mon 04:00 UTC | `raw_worldbank_indicators`, `raw_opensanctions_entities` |
| `stratum-core-pipeline` | event: when any `raw_*` updates | everything downstream through `score_country_threat_profiles` + `ontology_*` (use "build downstream of inputs" so the scheduler resolves the DAG) |
| `stratum-monthly-trade` | time: 1st of month | re-run Comtrade queue + baselines (trade data lags ~2 months) |

Tip: exclude the LLM transform from the event-triggered schedule if you
want cost control, and give it its own daily schedule — the cache makes
every run incremental anyway.

## Data Health checks

Add health checks (dataset > Health) on the load-bearing datasets:

- `clean_*`: **freshness** (updated within 8 days) + **row count > 0**.
- `clean_sipri_milex`: row count within ±20% of previous build (schema
  drift in a new SIPRI release shows up here first).
- `feature_contracts_llm_classified`: column check `needs_review` true-rate
  < 20% (LLM/json health).
- `threat_signals`: non-empty; alert if compound-signal count jumps > 5x
  build-over-build (either a real-world event or a thresholds bug — a
  human should look either way).
- Subscribe yourself to failures (Health > notifications).

## Logging & monitoring conventions already in the code

- Every transform logs rows-in/rows-out/dropped (`log_counts`) and
  unmatched country names (`log_unmatched`) — visible in build logs.
- All HTTP goes through `request_with_retry` (exponential backoff 2/4/8/16s
  + jitter, Retry-After honored).
- Comtrade/ACLED/USASpending ingests are incremental with
  checkpoint-by-output, so a failed build resumes where it left off.

## Idempotency guarantees

- Deterministic IDs everywhere (`stable_id`): contracts, flows, signals,
  transfers. Re-running any transform yields the same keys — no dupes, and
  ontology writeback edits (reviewed/notes) survive rebuilds.
- Clean transforms dedupe on their natural keys after every append-style
  ingest.

## Cost/quota guardrails

- Comtrade: `COMTRADE_DAILY_CALL_BUDGET = 450` (free tier 500/day).
- USASpending: `USASPENDING_MAX_PAGES_PER_RUN` caps a runaway backfill.
- LLM: `LLM_MAX_CONTRACTS_PER_RUN = 2000` + permanent cache.
- ACLED: monthly-ish refresh is plenty (weekly data updates).
