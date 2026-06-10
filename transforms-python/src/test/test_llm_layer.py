import pandas as pd
import pytest

from stratum.core.llm.json_guard import InvalidClassification, parse_classification
from stratum.core.llm.keyword_classifier import build_naics_psc_lookup, classify
from stratum.core.llm.prompts import build_prompt


def test_keyword_classifier_hypersonics():
    out = classify(
        "Design and flight test of a hypersonic glide vehicle with scramjet "
        "propulsion, including prototype demonstration."
    )
    assert "hypersonics" in out["capability_domains"]
    assert out["capability_maturity_stage"] == "development"
    assert out["threat_relevance_score"] > 0.3
    assert any("hypersonic" in k for k in out["technology_keywords"])


def test_keyword_classifier_none():
    out = classify("Office furniture and janitorial services for building 42.")
    assert out["capability_domains"] == ["none"]
    assert out["threat_relevance_score"] == 0.0


def test_keyword_classifier_uses_naics():
    ref = pd.DataFrame([{
        "code": "336414", "code_type": "NAICS",
        "description": "Guided Missile Manufacturing",
        "capability_domains": "missile_defense|hypersonics",
        "label_confidence": 0.9,
    }])
    lookup = build_naics_psc_lookup(ref)
    out = classify("Production of interstage assemblies.",
                   naics_code="336414", naics_psc_lookup=lookup)
    assert "missile_defense" in out["capability_domains"]


def test_json_guard_valid_and_repair():
    raw = """Here is the analysis:
    {"capability_domains": ["Hypersonics", "bogus_domain"],
     "technology_keywords": ["scramjet"],
     "threat_relevance_score": 1.7,
     "capability_maturity_stage": "DEVELOPMENT",
     "reasoning": "test"}"""
    out = parse_classification(raw)
    assert out["capability_domains"] == ["hypersonics"]  # bogus filtered, case fixed
    assert out["threat_relevance_score"] == 1.0          # clamped
    assert out["capability_maturity_stage"] == "development"


def test_json_guard_rejects_garbage():
    with pytest.raises(InvalidClassification):
        parse_classification("the model rambled with no json")
    with pytest.raises(InvalidClassification):
        parse_classification('{"capability_domains": [}')


def test_prompt_contains_taxonomy_and_inputs():
    p = build_prompt("Radar upgrade", "Dept of Defense", "Raytheon", 1_000_000)
    assert "Radar upgrade" in p
    assert "hypersonics" in p
    assert "1,000,000" in p
    assert "capability_maturity_stage" in p
