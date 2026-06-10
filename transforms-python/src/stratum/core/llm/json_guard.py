"""Validate / repair LLM classification output.

Quality requirement: if the model returns invalid JSON, the caller retries
(temperature=0, up to LLM_MAX_RETRIES); if it still fails, the contract is
flagged `needs_review` and falls back to the keyword classifier.
"""
from __future__ import annotations

import json
import re
from typing import Any

from stratum.core.llm.taxonomy import CAPABILITY_DOMAINS

VALID_STAGES = {"research", "development", "production", "sustainment", "unknown"}
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class InvalidClassification(ValueError):
    pass


def parse_classification(raw_text: str) -> dict[str, Any]:
    """Extract and validate the classification JSON from a model response.

    Raises InvalidClassification when unusable; callers decide retry/fallback.
    """
    match = _JSON_BLOCK.search(raw_text or "")
    if not match:
        raise InvalidClassification("no JSON object in response")
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise InvalidClassification(f"bad JSON: {e}") from e
    if not isinstance(obj, dict):
        raise InvalidClassification("JSON is not an object")

    domains = obj.get("capability_domains") or []
    if isinstance(domains, str):
        domains = [domains]
    domains = [d for d in (str(x).strip().lower() for x in domains)
               if d in CAPABILITY_DOMAINS and d != "none"]

    keywords = obj.get("technology_keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    keywords = [str(k).strip() for k in keywords if str(k).strip()][:10]

    try:
        score = float(obj.get("threat_relevance_score", 0.0))
    except (TypeError, ValueError) as e:
        raise InvalidClassification("threat_relevance_score not numeric") from e
    score = min(max(score, 0.0), 1.0)

    stage = str(obj.get("capability_maturity_stage", "unknown")).strip().lower()
    if stage not in VALID_STAGES:
        stage = "unknown"

    return {
        "capability_domains": domains,
        "technology_keywords": keywords,
        "threat_relevance_score": score,
        "capability_maturity_stage": stage,
        "reasoning": str(obj.get("reasoning", ""))[:500],
    }
