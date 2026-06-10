# Workshop Build Guide — the STRATUM application

One Workshop module, dark theme, seven pages. Use object-set variables
wired to the Ontology (not dataset-backed widgets) so clicks navigate the
object graph. Set the module-level theme to the dark/operations style —
this should read like a SCIF tool, not a BI dashboard.

Shared variables to create first:
- `selectedCountry` (object set: Country, single)
- `selectedSignal` (object set: ThreatSignal, single)
- `signalTypeFilter`, `domainFilter`, `tierFilter` (string filters)

---

## Page 1 — COMMAND CENTER

| Widget | Config |
|---|---|
| **Map** (full width) | Object set: all Country. Color polygons/markers by `threat_acceleration_index` (grey→yellow→orange→red stops at 0/25/50/75 to match C/B/A/S). On click → set `selectedCountry` + navigate to page 3. Tooltip: name, tier, `top_domains_of_concern[0]`, `last_signal_window`. |
| **4 metric cards** | (a) count Country where tier = S, (b) tier = A, (c) ThreatSignal where `created_at` within 7d, (d) ThreatSignal where `signal_type = compound_signal` within 30d. |
| **Object table — Active Signals** | ThreatSignal, filtered `reviewed = false`, sorted `signal_strength` desc. Columns: country, domain, type, strength (bar formatting), confidence, window. Row click → `selectedSignal` + open detail overlay. Top filter bar bound to the filter variables. |
| **Pivot/heatmap — Domain Heat Matrix** | Rows: `country_code` (monitored only), columns: `domain`, value: count of signals, cell color by count. |
| **Object table — Procurement accelerations** | Top accelerating recipient×domain pairs: back with `score_procurement_acceleration` filtered `domain_acceleration_flag = true`, sorted by `tempo_score` desc, 10 rows. |

## Page 2 — PROCUREMENT INTELLIGENCE (Layer 1)

- Left rail: filter list on ProcurementContract — agency, recipient
  country, `primary_capability_domain`, date range, min value,
  `capability_maturity_stage`, `needs_review` toggle; full-text search
  bound to `description_raw_text`.
- Timeline / bar-over-time of contract count by month, split by domain
  (chart widget on the filtered set; toggle count↔value via a variable).
- Main object table; row expansion shows `description_raw_text`, all
  `capability_domains`, `technology_keywords`, `classification_reasoning`,
  plus linked Country and Company.
- Line chart — Domain Velocity: monthly contract value per selected
  domains.
- Network/graph widget (if enabled on your stack): Company nodes sized by
  `total_contract_value_usd`, red border when `is_sanctioned`. Otherwise: a
  Company object table sorted by value with a sanctioned-filter chip.
- Bottom strip: histogram of `classification_confidence` + table of
  `needs_review = true` contracts with the **Mark Reviewed** Action button.

## Page 3 — COUNTRY DEEP-DIVE (primary analyst workspace)

Everything filters by `selectedCountry`.

- Header: name + tier badge + `threat_acceleration_index` +
  `capability_credibility_score` + `last_updated`; **Add Analyst Note**
  Action button.
- **Threat Signal Timeline:** ThreatSignal for country over `created_at`,
  color by `signal_type` (clustering = the story).
- **Domain Radar — THE core visual:** two overlaid polygons per domain
  axis: declared percentile vs material percentile from
  `score_material_credibility` (latest year). If the native chart set has
  no radar, options in order of effort: (a) grouped bar chart of the two
  percentiles per domain — same story, zero code; (b) OSDK custom widget
  (TypeScript + any radar chart lib) reading the same object set.
- **Budget vs Material panel:** left bars = SIPRI milex by year; right
  bars = defense-relevant import value by year; line = discrepancy.
- **Trade flows table:** CommodityFlow linked to country, grouped by
  `capability_category`, sorted `anomaly_score` desc.
- **Arms transfers panel:** received + supplied ArmsTransfer tables, TIV
  trend chart.
- **Conflict context:** intensity line (12m) + small map of ConflictEvent
  within the country.
- **Active signals list** with `supporting_evidence` links → click jumps to
  the evidence object view.
- **Lead-time callout:** `lead_time_min_months`–`lead_time_max_months`,
  color: >36 green / 18–36 yellow / <18 red.

## Page 4 — MATERIAL CREDIBILITY ENGINE (Layer 2)

- Left: Country leaderboard table — `capability_credibility_score`,
  under/over-declaration scores, red→green color scale; click sets
  `selectedCountry`.
- Treemap (or pivot fallback): country × HS code sized by import value,
  colored by `anomaly_score`.
- Anomalous flows table: `anomaly_score > 0.5`, sorted by deviation desc.
- **Budget credibility scatter:** X = SIPRI milex (log), Y = defense-HS
  import value (log), one point per country, diagonal = credible band;
  above = under-declaring, below = budget theater.
- Sankey/provenance (needs `COMTRADE_PARTNER_DETAIL = True` so partner
  routes exist): source → destination for the selected commodity, flag
  sanctioned origins.

## Page 5 — THREAT SIGNAL MANAGEMENT (analyst workflow)

- Queue: ThreatSignal `reviewed = false`, sorted by
  `signal_strength * confidence_score` (add as a derived column), bulk
  Action buttons: Mark Reviewed / Dismiss / Escalate.
- Detail panel (on `selectedSignal`): full description, evidence list with
  inline charts, `analyst_notes` editor (Add Analyst Note Action).
- Correlation view: other signals same country (other domains) and same
  domain (other countries).
- **Generate Intelligence Report** button → `generate_intel_report` AIP
  Logic function with the selected signals → render markdown → export.

## Page 6 — COMPANY INTELLIGENCE

Company search + profile (contract history via linked contracts), anomaly
chips (new-domain entries, value spikes), `is_sanctioned` filter, and a map
of place-of-performance if you geocode later.

## Page 7 — SYSTEM HEALTH & DATA FRESHNESS

- Pipeline status grid: builds + last success per transform (link the
  datasets; the build status chips come free with dataset widgets).
- Freshness cards: max(`ingest_window_end`) for USASpending, max year in
  Comtrade, max `event_date` ACLED/GDELT, SIPRI release year.
- Classification health: confidence histogram + `needs_review` count over
  time.
- Comtrade queue: pending (reporter, year) count = target set minus
  distinct pairs present (small derived dataset if you want it exact).

---

### Contour
Create four Contour analyses on: `feature_contracts_llm_classified`,
`feature_comtrade_with_baselines`, monthly profile snapshots, and a
signal-effectiveness join (signals vs subsequent ACLED/GDELT activity).
Save them in `applications/` — judges look for Contour fluency as the
ad-hoc layer next to the Workshop product.
