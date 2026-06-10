"""Transform 3.1 — feature_contracts_merged -> feature_contracts_llm_classified.

The core intelligence layer: classifies every contract description into
capability domains, technology keywords, threat relevance, and maturity
stage. Three modes (stratum/config.py LLM_MODE):

  "aip"      — AIP language model inside the transform (palantir_models).
               Default; set AIP_MODEL_RID to a model your enrollment has.
  "keyword"  — deterministic keyword/NAICS classifier. No LLM required;
               useful before AIP access is approved.
  "external" — fine-tuned Mistral-7B behind an OpenAI-compatible endpoint
               (e.g. llama-cpp-python server), reached via an External
               Transform Source whose RID you set below.

Incremental contract: already-classified contract_ids are NEVER re-sent to
the model (cache lives in the output dataset itself); each run classifies
up to LLM_MAX_CONTRACTS_PER_RUN new contracts. Invalid JSON retries up to
LLM_MAX_RETRIES at temperature 0, then falls back to the keyword
classifier with needs_review=True.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
from pyspark.sql import types as T
from transforms.api import Input, Output, incremental, transform

from stratum import config
from stratum.core.llm import keyword_classifier
from stratum.core.llm.json_guard import InvalidClassification, parse_classification
from stratum.core.llm.prompts import build_prompt
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)

# External-mode endpoint source (OpenAI-compatible /v1/chat/completions).
MISTRAL_SOURCE_RID = "ri.magritte..source.REPLACE_ME"
MISTRAL_MODEL_NAME = "stratum-mistral-7b-procurement"

SCHEMA = T.StructType([
    T.StructField("contract_id", T.StringType()),
    T.StructField("source", T.StringType()),
    T.StructField("recipient_name", T.StringType()),
    T.StructField("recipient_country", T.StringType()),
    T.StructField("awarding_agency", T.StringType()),
    T.StructField("award_date", T.TimestampType()),
    T.StructField("total_value_usd", T.DoubleType()),
    T.StructField("description_raw_text", T.StringType()),
    T.StructField("naics_code", T.StringType()),
    T.StructField("psc_code", T.StringType()),
    T.StructField("capability_domains", T.ArrayType(T.StringType())),
    T.StructField("primary_capability_domain", T.StringType()),
    T.StructField("technology_keywords", T.ArrayType(T.StringType())),
    T.StructField("threat_relevance_score", T.DoubleType()),
    T.StructField("capability_maturity_stage", T.StringType()),
    T.StructField("classification_reasoning", T.StringType()),
    T.StructField("classifier", T.StringType()),
    T.StructField("classification_confidence", T.DoubleType()),
    T.StructField("needs_review", T.BooleanType()),
    T.StructField("classified_at", T.StringType()),
])


def _classify_batch(pdf: pd.DataFrame, naics_lookup: dict, call_llm) -> pd.DataFrame:
    """Apply LLM (if provided) with keyword fallback; returns SCHEMA columns."""
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for row in pdf.itertuples(index=False):
        result = None
        if call_llm is not None:
            prompt = build_prompt(row.description_raw_text, row.awarding_agency,
                                  row.recipient_name, row.total_value_usd)
            for attempt in range(config.LLM_MAX_RETRIES):
                try:
                    result = parse_classification(call_llm(prompt))
                    result["classifier"] = "llm"
                    result["classification_confidence"] = 0.9
                    result["needs_review"] = False
                    break
                except InvalidClassification as exc:
                    log.warning("invalid LLM JSON for %s (try %d/%d): %s",
                                row.contract_id, attempt + 1,
                                config.LLM_MAX_RETRIES, exc)
                except Exception as exc:
                    log.warning("LLM call failed for %s: %s", row.contract_id, exc)
        if result is None:
            result = keyword_classifier.classify(
                row.description_raw_text, naics_code=row.naics_code,
                psc_code=row.psc_code, naics_psc_lookup=naics_lookup)
            result["needs_review"] = call_llm is not None  # LLM failed hard
            result.setdefault("classifier", "keyword")
        domains = result["capability_domains"]
        results.append({
            "contract_id": row.contract_id,
            "source": row.source,
            "recipient_name": row.recipient_name,
            "recipient_country": row.recipient_country,
            "awarding_agency": row.awarding_agency,
            "award_date": row.award_date,
            "total_value_usd": row.total_value_usd,
            "description_raw_text": row.description_raw_text,
            "naics_code": row.naics_code,
            "psc_code": row.psc_code,
            "capability_domains": domains,
            "primary_capability_domain": domains[0] if domains else "none",
            "technology_keywords": result["technology_keywords"],
            "threat_relevance_score": float(result["threat_relevance_score"]),
            "capability_maturity_stage": result["capability_maturity_stage"],
            "classification_reasoning": result.get("reasoning", ""),
            "classifier": result.get("classifier", "keyword"),
            "classification_confidence": float(
                result.get("classification_confidence", 0.9)),
            "needs_review": bool(result.get("needs_review", False)),
            "classified_at": now,
        })
    return pd.DataFrame(results, columns=[f.name for f in SCHEMA.fields])


def _select_todo(contracts, out, naics_ref) -> tuple[pd.DataFrame, dict]:
    from stratum.datasets._util import previous_ids

    done = previous_ids(out, SCHEMA, "contract_id")
    pdf = contracts.dataframe().toPandas()
    todo = pdf[~pdf["contract_id"].isin(done)]
    todo = todo.sort_values("award_date", ascending=False) \
               .head(config.LLM_MAX_CONTRACTS_PER_RUN)
    log.info("llm_classified: %d total, %d cached, %d to classify this run",
             len(pdf), len(done), len(todo))
    lookup = keyword_classifier.build_naics_psc_lookup(
        naics_ref.dataframe().toPandas())
    return todo, lookup


if config.LLM_MODE == "aip":
    from palantir_models.transforms import OpenAiGptChatLanguageModelInput

    @incremental(snapshot_inputs=["contracts", "naics_ref"])
    @transform(
        out=Output(config.features("feature_contracts_llm_classified")),
        contracts=Input(config.features("feature_contracts_merged")),
        naics_ref=Input(config.reference("ref_naics_domain_mapping")),
        model=OpenAiGptChatLanguageModelInput(config.AIP_MODEL_RID),
    )
    def compute(ctx, out, contracts, naics_ref, model):
        from language_model_service_api.languagemodelservice_api import (
            ChatMessage, ChatMessageRole)
        from language_model_service_api.languagemodelservice_api_completion_v3 import (
            GptChatCompletionRequest)

        def call_llm(prompt: str) -> str:
            req = GptChatCompletionRequest(
                [ChatMessage(ChatMessageRole.USER, prompt)],
                temperature=0.0, max_tokens=700)
            return model.create_chat_completion(req).completion

        todo, lookup = _select_todo(contracts, out, naics_ref)
        out.write_dataframe(to_spark(ctx, _classify_batch(todo, lookup, call_llm), SCHEMA))

elif config.LLM_MODE == "external":
    from transforms.external.systems import Source, external_systems

    @incremental(snapshot_inputs=["contracts", "naics_ref"])
    @external_systems(mistral=Source(MISTRAL_SOURCE_RID))
    @transform(
        out=Output(config.features("feature_contracts_llm_classified")),
        contracts=Input(config.features("feature_contracts_merged")),
        naics_ref=Input(config.reference("ref_naics_domain_mapping")),
    )
    def compute(ctx, out, contracts, naics_ref, mistral):
        conn = mistral.get_https_connection()
        client, base = conn.get_client(), conn.url

        def call_llm(prompt: str) -> str:
            resp = client.post(
                f"{base}/v1/chat/completions",
                json={"model": MISTRAL_MODEL_NAME, "temperature": 0.0,
                      "max_tokens": 700,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=180)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        todo, lookup = _select_todo(contracts, out, naics_ref)
        out.write_dataframe(to_spark(ctx, _classify_batch(todo, lookup, call_llm), SCHEMA))

else:  # "keyword" — no model required
    @incremental(snapshot_inputs=["contracts", "naics_ref"])
    @transform(
        out=Output(config.features("feature_contracts_llm_classified")),
        contracts=Input(config.features("feature_contracts_merged")),
        naics_ref=Input(config.reference("ref_naics_domain_mapping")),
    )
    def compute(ctx, out, contracts, naics_ref):
        todo, lookup = _select_todo(contracts, out, naics_ref)
        out.write_dataframe(to_spark(ctx, _classify_batch(todo, lookup, None), SCHEMA))
