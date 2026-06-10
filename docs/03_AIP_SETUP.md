# AIP Setup — LLM classification + report generation + agent

Three AIP touchpoints, in build order.

## 1. LLM classification in the pipeline (Transform 3.1)

`stratum/datasets/features/llm_classified.py` supports three modes via
`config.LLM_MODE`:

### Mode "aip" (default — recommended for the challenge)
Uses an AIP-provisioned language model *inside the transform* through
`palantir_models`.

1. Confirm AIP is enabled on your enrollment (AIP menu visible) and that a
   GPT/Claude model is available under **AIP > Models** (or Model catalog).
2. Copy the model RID into `config.AIP_MODEL_RID`. The default targets a
   GPT-4o-class model; any chat model works — the prompt asks for strict
   JSON and `json_guard` validates/repairs.
3. Add the `palantir_models` library in the repo's Libraries panel.
4. If you pick a Claude-family model and the GPT request classes don't
   apply on your stack, swap `OpenAiGptChatLanguageModelInput` for the
   generic chat-completion input class shown in your enrollment's
   palantir_models docs snippet (one import + one call-site change,
   isolated in `_call` inside the transform).

Cost/scale controls: `LLM_MAX_CONTRACTS_PER_RUN` (default 2000/build) and
the permanent classification cache (already-classified contract IDs are
never re-sent).

### Mode "keyword"
No model at all — deterministic keyword + NAICS/PSC classifier. Use this to
get the pipeline running end-to-end before AIP access, then flip to "aip";
only new contracts get LLM treatment (cache keeps the old labels until you
wipe the output dataset to force re-classification).

### Mode "external"
Your fine-tuned Mistral-7B (see `model-training/`) served as an
OpenAI-compatible endpoint (llama-cpp-python server, vLLM, etc. on a box
you control). Create a REST source for it (egress + import-to-repo), paste
the RID into `MISTRAL_SOURCE_RID` in the transform module.

## 2. "Generate Intelligence Report" (AIP Logic)

Build in **AIP Logic** (applications folder), name it
`generate_intel_report`:

1. **Input:** `signals` — list of ThreatSignal objects (Workshop passes the
   analyst's selection).
2. **Block 1 — fetch context (tools):** for each signal's `country_code`,
   fetch the Country object; collect `supporting_evidence` IDs and look up
   the matching ProcurementContract / CommodityFlow objects.
3. **Block 2 — Use LLM:** paste the prompt below, wiring the inputs.
4. **Output:** string (markdown report).

Prompt for the LLM block:

```
You are drafting an intelligence assessment from STRATUM, an OSINT threat
platform. Using ONLY the structured inputs below, write a report with
exactly these sections:
Executive Summary / Observed Signals / Supporting Evidence /
Confidence Assessment / Recommended Action.

Rules: cite concrete figures (deviation %, contract values, TIV) from the
inputs; do not invent facts not present in the inputs; note that all data
is open-source and unclassified; keep it under 600 words; plain
professional tone, no hedging boilerplate.

COUNTRY PROFILE: {country_object_properties}
SIGNALS: {signal_list_with_descriptions_strengths_confidences}
EVIDENCE: {evidence_rows}
```

The deterministic skeleton in `stratum/core/report.py` is the fallback and
the structure reference — AIP Logic should produce the same five sections.
Wire the function to Workshop (button on the Signal Detail panel: "Generate
Intelligence Report" → show output in a markdown widget / export).

## 3. AIP Agent (bonus, Agent Studio)

Create an agent "STRATUM Analyst Assistant":

- **Tools:** Ontology query access to Country, ThreatSignal,
  CommodityFlow, ProcurementContract (read-only); optionally the
  `generate_intel_report` Logic function.
- **System prompt:** "You answer analyst questions about state-actor
  capability development using the STRATUM ontology. Always query the
  ontology rather than answering from memory; cite object IDs; offer the
  intelligence-report function when the analyst wants a document."
- Test queries: "Show countries with material anomalies in rare-earth
  imports in the last 6 months", "Why is IRN tier A?", "Which sanctioned
  companies received contracts?".

## Quality gates (from the build spec)

- Invalid JSON → retried at temperature 0 up to 3x, then keyword fallback
  with `needs_review = true` (already implemented in the transform).
- Track the classification confidence distribution on the Workshop System
  Health page; a drift downward means the prompt or model changed.
- The fine-tuned model is only swapped in when it clears F1 > 0.78 on
  validation (`model-training/evaluate.py` prints the gate).
