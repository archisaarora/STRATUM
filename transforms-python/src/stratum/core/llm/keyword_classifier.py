"""Deterministic keyword/NAICS classifier.

Three jobs:
  * LLM_MODE="keyword" — sole classifier (no model required),
  * fallback when LLM output stays invalid after retries,
  * weak-label generator for fine-tuning data (Stage 5.1 bootstrapping).
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from stratum.core.llm.taxonomy import DOMAIN_KEYWORDS, MATURITY_KEYWORDS

_WORDISH = re.compile(r"[a-z0-9][a-z0-9\- ]*")


def _compile_bank(bank: dict[str, list[str]]) -> dict[str, list[re.Pattern]]:
    compiled = {}
    for label, terms in bank.items():
        compiled[label] = [
            re.compile(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])")
            for t in terms
        ]
    return compiled


_DOMAIN_PATTERNS = _compile_bank(DOMAIN_KEYWORDS)
_MATURITY_PATTERNS = _compile_bank(MATURITY_KEYWORDS)


def build_naics_psc_lookup(ref: pd.DataFrame) -> dict[str, list[str]]:
    """ref_naics_domain_mapping -> {code: [domains]}."""
    lookup: dict[str, list[str]] = {}
    for row in ref.itertuples(index=False):
        lookup[str(row.code).strip()] = [
            d for d in str(row.capability_domains).split("|") if d
        ]
    return lookup


def classify(
    description: str,
    *,
    naics_code: str | None = None,
    psc_code: str | None = None,
    naics_psc_lookup: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Classify one contract description. Returns the same shape as the
    LLM classification plus a confidence estimate."""
    text = (description or "").lower()
    domain_hits: dict[str, list[str]] = {}
    for domain, patterns in _DOMAIN_PATTERNS.items():
        hits = [p.pattern for p in patterns if p.search(text)]
        if hits:
            domain_hits[domain] = hits

    # NAICS/PSC mapping contributes domains with a single "hit" weight.
    code_domains: list[str] = []
    if naics_psc_lookup:
        for code in (naics_code, psc_code):
            if code and str(code).strip() in naics_psc_lookup:
                code_domains.extend(naics_psc_lookup[str(code).strip()])
    for d in code_domains:
        domain_hits.setdefault(d, []).append("naics_psc")

    ranked = sorted(domain_hits.items(), key=lambda kv: len(kv[1]), reverse=True)
    domains = [d for d, _ in ranked[:4]]

    keywords: list[str] = []
    seen = set()
    for domain in domains:
        for p in _DOMAIN_PATTERNS.get(domain, []):
            m = p.search(text)
            if m and m.group(0) not in seen:
                seen.add(m.group(0))
                keywords.append(m.group(0))
    keywords = keywords[:10]

    stage_scores = {
        stage: sum(1 for p in patterns if p.search(text))
        for stage, patterns in _MATURITY_PATTERNS.items()
    }
    best_stage = max(stage_scores, key=lambda s: stage_scores[s])
    stage = best_stage if stage_scores[best_stage] > 0 else "unknown"

    total_hits = sum(len(h) for h in domain_hits.values())
    relevance = 0.0
    if domains:
        # 1 hit -> ~0.3, saturates toward 0.9 with many independent hits
        relevance = min(0.9, 0.2 + 0.1 * total_hits)
    confidence = min(0.85, 0.25 + 0.1 * total_hits) if domains else 0.3

    return {
        "capability_domains": domains or ["none"],
        "technology_keywords": keywords,
        "threat_relevance_score": round(relevance, 3),
        "capability_maturity_stage": stage,
        "reasoning": (
            f"keyword classifier: {total_hits} keyword/code hits across "
            f"{len(domain_hits)} domains" if domains else
            "keyword classifier: no capability keywords matched"
        ),
        "classification_confidence": round(confidence, 3),
        "classifier": "keyword",
    }
