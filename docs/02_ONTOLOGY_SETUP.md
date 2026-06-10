# Ontology Setup (Ontology Manager)

The Ontology is the center of gravity: analysts navigate Country →
ThreatSignal → evidence objects, and every analyst write-back is an Action.
Each object type below is backed by one `ontology_*` dataset produced by the
pipeline (`data/ontology/`).

Work on an **Ontology branch** while editing, then propose/merge — don't
edit the default branch live.

## Object types

Create each via Ontology Manager > New > Object type > "from dataset",
selecting the backing dataset. Set the primary key, title property, and
property types as listed (most types are inferred; fix arrays and booleans
if inference misses them).

### 1. Country — backing: `ontology_country`
- Primary key: `country_code` · Title: `country_name`
- Properties: `region`, `is_nato` (bool), `is_monitored` (bool),
  `gdp_usd`, `gdp_growth_pct`, `population`,
  `declared_defense_budget_usd`, `worldbank_milex_usd`, `defense_pct_gdp`,
  `budget_discrepancy_flag` (bool), `threat_acceleration_index` (double),
  `capability_credibility_score` (double), `composite_threat_tier`,
  `top_domains_of_concern` (string array), `active_signal_count`,
  `compound_signal_count`, `dominant_maturity_stage`,
  `lead_time_min_months`, `lead_time_max_months`, `active_conflict` (bool),
  `last_updated`
- Icon: flag/globe; color by `composite_threat_tier` in views.

### 2. ProcurementContract — backing: `ontology_procurement_contract`
- PK: `contract_id` · Title: `recipient_name`
- Notable: `capability_domains` + `technology_keywords` (string arrays),
  `threat_relevance_score` (double), `capability_maturity_stage`,
  `needs_review` (bool), `description_raw_text` (long text),
  `classifier`, `classification_confidence`.

### 3. Company — backing: `ontology_company`
- PK: `company_id` · Title: `company_name`
- Notable: `is_sanctioned` / `opensanctions_match` (bool),
  `total_contract_value_usd`, `contract_count`,
  `primary_capability_domain`, `country_of_incorporation`.

### 4. CommodityFlow — backing: `ontology_commodity_flow`
- PK: `flow_id` · Title: `commodity_name`
- Notable: `country_code`, `hs_code`, `capability_category`,
  `flow_direction`, `trade_value_usd`, `year`,
  `baseline_deviation_pct`, `anomaly_score`, `anomaly_flag` (bool).

### 5. ThreatSignal — backing: `ontology_threat_signal`
- PK: `signal_id` · Title: `description_text`
- Notable: `signal_type`, `country_code`, `domain`,
  `signal_strength` (double), `confidence_score` (double),
  `supporting_evidence` (string array), `window_end`, `created_at`,
  `reviewed` (bool), `analyst_notes` (long text).

### 6. ArmsTransfer — backing: `ontology_arms_transfer`
- PK: `transfer_id` · Title: `weapon_designation`
- Notable: `supplier_country`, `recipient_country`, `weapon_description`,
  `order_year`, `delivery_year_last`, `total_tiv`, `status`.

### 7. ConflictEvent — backing: `ontology_conflict_event`
- PK: `event_id` · Title: `event_type`
- Notable: `event_date`, `country_code`, `latitude`/`longitude`
  (set as a geo point if you enable geo typing), `fatalities`,
  `actors_involved` (string array), `event_source`.

## Link types

All links join on country code / id properties (Ontology Manager > New >
Link type > foreign-key link):

| Link | Cardinality | Join |
|---|---|---|
| Country **has_procurement** ProcurementContract | 1:N | `country_code` = `recipient_country` |
| Company **received_contract** ProcurementContract | 1:N | `company_name` ≈ `recipient_name` (or add `company_id` to the contract export for an exact key) |
| Country **has_trade_flow** CommodityFlow | 1:N | `country_code` |
| Country **has_threat_signal** ThreatSignal | 1:N | `country_code` |
| Country **supplied_arms** ArmsTransfer | 1:N | `country_code` = `supplier_country` |
| Country **received_arms** ArmsTransfer | 1:N | `country_code` = `recipient_country` |
| Country **has_conflict_event** ConflictEvent | 1:N | `country_code` |
| Company **incorporated_in** Country | N:1 | `country_of_incorporation` |

ThreatSignal ↔ evidence (contracts / flows) is carried by the
`supporting_evidence` ID array; for first-class N:M links, build small join
datasets (signal_id, contract_id) by exploding that array in a transform
and back the link with them — worth doing if time allows, the Workshop
evidence panel gets cleaner.

## Actions (all analyst writes go through Actions — never edit datasets)

Create in Ontology Manager > Actions:

1. **Add Analyst Note** — modifies ThreatSignal: appends to
   `analyst_notes` (parameters: note text). Submission criteria: note
   non-empty.
2. **Mark Signal Reviewed** — sets `reviewed = true` (bulk-enabled).
3. **Dismiss Signal** — sets `reviewed = true` and prefixes
   `analyst_notes` with `DISMISSED: {reason}` (parameter: reason).
4. **Escalate Signal** — sets a `analyst_notes` prefix `ESCALATED`; pair it
   with the AIP Logic report function (03 doc) in Workshop.

Note on writeback vs. pipeline rebuilds: Action edits live in the ontology
writeback layer. The signal generator emits **deterministic signal_ids**,
so rebuilds upsert the same objects and your `reviewed`/`analyst_notes`
edits survive refreshes.

## Object views

Give each object type a sensible default view (Object view editor):
Country view = profile header + linked signals table + linked flows;
ThreatSignal view = description, strength/confidence, evidence list.
Analysts will land on these from Object Explorer and Workshop links.
