# STRATUM
### Seeing what states *do*, not what they *say*

*A Palantir Build Challenge submission — geopolitical threat-capability
intelligence from entirely open sources.*

---

## 1. The problem

Every government in the world publishes a defense budget. Almost none of
them are true. A state that wants to build a capability quietly does not
announce it and does not import finished weapons — those are visible,
sanctionable, and embargoed. Instead it imports the **inputs**: propellant
chemicals, titanium billet, ferroalloys, guidance-grade integrated
circuits, machine tools. On a customs manifest these look like ordinary
industrial trade. Spread across dozens of commodity codes and a hundred
trading partners, they are invisible to any analyst watching one database
at a time.

The intelligence question STRATUM answers is therefore not "what did this
country announce?" but:

> **Is this country's physical behavior — what it buys, from whom, how
> fast — consistent with the military posture it declares? And when it
> diverges, in which capability domain, and how close is that capability
> to being operational?**

This is real tradecraft. Analysts at DIA, the combatant commands, and
Treasury/OFAC do versions of it by hand. STRATUM does it continuously,
across every monitored country and every defense-relevant commodity, and
surfaces only the convergences a human should look at.

---

## 2. What it does — the three intelligence layers

STRATUM fuses ten open data sources into a single ontology and reasons
across three layers.

### Layer 1 — Procurement Language Intelligence
Every government contract description (USASpending; DoD announcements) is
classified into an **18-domain capability taxonomy** (hypersonics,
directed energy, electronic warfare, nuclear, naval, biodefense, …) with
extracted technology keywords, a threat-relevance score, and a
**capability-maturity stage** (research → development → production →
sustainment). The maturity stage is what lets STRATUM estimate *lead time
to operational capability*, not just "activity exists." Locally this runs
on a deterministic keyword/NAICS classifier; in Foundry the same prompt
and taxonomy drive an AIP LLM, with a fine-tuned Mistral-7B as the
production path.

### Layer 2 — Material Credibility (the core of the product)
For every country this layer answers "do the physical imports match the
declared budget?" three ways:

- **Commodity anomaly detection.** Each (country, commodity) import series
  is benchmarked against its own 3-year rolling baseline; a blended
  deviation/z-score flags imports far above the country's own norm.
- **Import-intensity forensics — the under-the-radar detector.**
  Defense-relevant imports are split into two streams: **direct military
  goods** (arms, warships, combat aircraft — the visible category) and
  **dual-use precursors** (the chemicals, metals, and electronics you build
  capability *from*). STRATUM computes each country's import-to-declared-
  budget intensity ratio, z-scores it against peers, and raises a
  **covert-acquisition flag** when dual-use imports surge while direct
  imports and the declared budget stay flat. That specific divergence is
  the signature of building capability outside declared channels.
- **Budget credibility.** SIPRI's declared military expenditure is cross-
  checked against the World Bank's independently compiled figure; a >15%
  divergence is flagged. Material evidence is then ranked against declared
  programs by cross-country percentile, producing per-country
  **under-declaration** and **over-declaration** scores.

### Layer 3 — Anomaly Detection & Threat Scoring
A transparent rule engine emits discrete, evidence-linked **ThreatSignals**:

| Signal | Fires when |
|---|---|
| `material_anomaly` | a commodity import is >100% above its 3-yr baseline with a high anomaly score |
| `covert_acquisition` | dual-use imports surge >50% YoY while direct imports stay flat and intensity is elevated vs peers |
| `budget_discrepancy` | SIPRI vs World Bank diverge >15%, or material evidence outranks declared spend |
| `procurement_acceleration` | 12-month contract count >2× the prior year **and** value up >50% |
| `arms_transfer_spike` | TIV deliveries received >2× the 3-yr rolling average |
| `compound_signal` | **≥2 of the above, independent, converge on the same country + domain inside 6 months** |

The compound signal is the heart of it. Any one indicator is noise; the
**convergence** of independent indicators — a budget that doesn't add up,
*and* precursor imports spiking, *and* contracts accelerating in the same
domain — is the non-obvious pattern a human analyst would need to assemble
by hand across four databases. STRATUM finds it automatically and escalates
it (geometric mean of component strengths × 1.5).

Signals roll up into a per-country **Threat Acceleration Index (0–100)** →
tier **S/A/B/C**, with the top domains of concern, a material-credibility
score, and a lead-time estimate.

### News corroboration (live)
From any signal, one click queries the **GDELT global news index** (65
languages, free, keyless) for recent reporting on that country and
capability domain — turning "the trade data says X" into "the trade data
says X, and here are seven articles from the regional press that corroborate
it." Notably, the *absence* of press coverage on a strong material signal
is itself intelligence: it means the activity is happening quietly.

---

## 3. Walkthrough: how a threat level is actually established

Take the demonstrator's planted scenario (synthetic, but mechanically
identical to how real data flows):

1. **Iran's propellant-precursor imports triple** in the latest year
   (HS 3601 propellant powders, 2814 ammonia) — `material_anomaly` fires
   in the `propellants_and_explosives` domain.
2. **Iran's declared budget stays flat** and disagrees with the World Bank
   figure — `budget_discrepancy` fires.
3. The import-intensity layer sees **dual-use up sharply while direct arms
   imports are flat** — `covert_acquisition` fires.
4. Three independent signal types now occupy the same country + 6-month
   window → **`compound_signal`**, escalated.
5. Those weighted signal strengths feed the Threat Acceleration Index →
   Iran lands at **Tier A**, top domain `propellants_and_explosives`, with a
   lead-time band from the maturity stage of any related contracts.
6. The analyst opens the Country Deep-Dive, sees the dual-use-vs-direct
   import chart (red rising, blue flat — the signature), drills into the
   specific commodity with its baseline band and anomaly markers, clicks
   **Find corroborating news**, and clicks **Generate Intelligence Report**
   for a structured product in seconds.

Every number on that screen traces back to a specific customs record or
contract. Nothing is a black box.

---

## 4. Why this is novel — not a dashboard anyone could rebuild

- **The fusion is the product, not the charts.** The hard, defensible part
  is cross-referencing *declared intent* (budgets, contracts) against
  *physical reality* (commodity flows, arms transfers) on a common ontology
  and scoring the **divergence**. A BI dashboard shows you one dataset
  prettily; STRATUM reasons across ten to find what no single dataset
  reveals.
- **The covert-acquisition / dual-use split is a genuine analytic insight,**
  not a visualization. Separating precursor imports from finished-weapon
  imports and flagging the divergence is exactly how proliferation analysts
  think — and it is encoded here as a reproducible, tested algorithm.
- **Compound signals surface the non-obvious.** The value is catching the
  convergence a human watching four separate tools would miss.
- **Everything is auditable.** Transparent statistics with documented
  thresholds, every signal carrying its evidence IDs. In a domain where an
  analyst has to defend a call, an unexplainable model score is worthless.
- **It degrades gracefully and runs on free data.** No classified inputs,
  no paid feeds required. Any source can be missing and the rest still
  produce signals.

---

## 5. Application — for the U.S. government

- **Indications & Warning.** Continuous, automated I&W on adversary
  capability development from open sources — a persistent tripwire that
  flags where to point expensive collection (satellites, HUMINT) *before* a
  capability is fielded. The lead-time estimate is the actionable output:
  it converts "something is happening" into "you have an estimated window."
- **Sanctions & export-control targeting (Treasury/BIS).** The dual-use
  surge detector points directly at which commodities and which supplier
  relationships are filling a capability gap — i.e., where a new control or
  designation would bite. The OpenSanctions cross-reference already flags
  sanctioned entities appearing in procurement.
- **Budget-deception detection.** Quantifies which states systematically
  under-declare military spending and by roughly how much — directly
  relevant to arms-control verification and threat assessment.
- **Analyst force multiplier.** One analyst can monitor every country at
  once; the system triages the queue so human attention goes to the
  highest-priority convergences, with a generated first-draft report.

## 6. Application — for Palantir

STRATUM is built to be **Foundry-native**, and it exercises the platform's
differentiators rather than just running code on it:

- **Ontology as the center of gravity** — Country, ThreatSignal,
  CommodityFlow, Company, ArmsTransfer, ConflictEvent as linked objects an
  analyst navigates, exactly the Foundry pattern.
- **AIP** for the procurement-classification LLM *and* AIP Logic for
  one-click intelligence-report generation; an optional AIP Agent answers
  natural-language questions against the ontology.
- **Actions** for every analyst write-back (review, escalate, annotate),
  governed and audited.
- **Pipeline lineage** — a clean raw → clean → features → scores → signals
  DAG that demonstrates the data-engineering story end to end.

It is a textbook example of the kind of decision-support application
Foundry exists to enable — and the local Streamlit build proves the entire
analytic works before a single Foundry resource is provisioned.

---

## 7. Tech stack (summary)

- **Python end-to-end** — identical pandas/NumPy business logic runs locally
  *and* inside Foundry transforms; nothing is reimplemented to deploy.
- **Data:** USASpending, UN Comtrade, World Bank, SIPRI (milex + arms),
  OpenSanctions, UCDP/ACLED, GDELT — all open, most keyless. Resumable,
  checkpointed fetchers; keyless fallbacks (Comtrade public API, UCDP for
  ACLED).
- **Analytics:** transparent statistics — rolling baselines, peer
  z-scores, percentile ranks, a documented rule engine. No black boxes.
- **LLM:** AIP model in production, deterministic keyword classifier as the
  zero-dependency fallback, fine-tuned Mistral-7B (QLoRA) as the
  self-hosted path.
- **App:** Streamlit + Plotly — six cross-linked, fully interactive pages
  (clickable world map, deep dives, forensics, signal triage, health).
- **Quality:** 50+ automated tests including a full-pipeline integration
  test and a headless dashboard render test; deterministic IDs make every
  re-run idempotent and preserve analyst state.
- **Deployment:** the same repository drops into a Foundry Code Repository;
  External Transforms, Ontology, AIP, and Workshop wrap the identical core.

---

## 8. Roadmap (honest about depth vs. concept)

The methodology is real and the demonstrator runs on real data. Path to an
operational tool:

1. **Monthly + partner-level Comtrade** (the subscription key unlocks this)
   → transshipment / re-export tracing: not just *what* a country imports
   but *who supplies it and through which intermediaries*.
2. **Entity resolution** beyond name-matching (corporate ownership graphs)
   so front companies and subsidiaries don't slip the sanctions screen.
3. **Historical backtesting** — replay 2015→present and measure how often
   signals preceded real fielded capabilities, to calibrate thresholds and
   publish a true-positive rate.
4. **Full Foundry deployment** with scheduled refresh and the AIP Agent, in
   an environment where government analysts could actually use it.

*All figures in the demonstrator are synthetic. STRATUM processes only
publicly available data and produces OSINT estimates, not classified
assessments.*
