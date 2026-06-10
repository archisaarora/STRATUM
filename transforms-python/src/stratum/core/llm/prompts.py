"""Prompt template for procurement classification (build-prompt Stage 3.1).

The same template is used for AIP model calls, the fine-tuned Mistral
endpoint, and fine-tuning data construction — keeping train and inference
distributions identical.
"""
from __future__ import annotations

from stratum.core.llm.taxonomy import CAPABILITY_DOMAINS

TAXONOMY_LINE = ", ".join(CAPABILITY_DOMAINS)

PROMPT_TEMPLATE = """You are a defense procurement intelligence analyst. Analyze the following government contract description and extract structured intelligence.

CONTRACT DESCRIPTION:
{description_text}

AWARDING AGENCY: {awarding_agency}
RECIPIENT: {recipient_name}
VALUE: ${total_value_usd}

Return a JSON object with exactly these fields:
{{
  "capability_domains": [list of applicable domains from the taxonomy],
  "technology_keywords": [list of specific technologies mentioned],
  "threat_relevance_score": float between 0 and 1,
  "capability_maturity_stage": "research" | "development" | "production" | "sustainment" | "unknown",
  "reasoning": "one sentence explaining your classification"
}}

Capability domain taxonomy: {taxonomy}"""


def build_prompt(
    description_text: str,
    awarding_agency: str | None,
    recipient_name: str | None,
    total_value_usd: float | None,
) -> str:
    value = f"{total_value_usd:,.0f}" if total_value_usd else "unknown"
    return PROMPT_TEMPLATE.format(
        description_text=(description_text or "")[:6000],
        awarding_agency=awarding_agency or "unknown",
        recipient_name=recipient_name or "unknown",
        total_value_usd=value,
        taxonomy=TAXONOMY_LINE,
    )
