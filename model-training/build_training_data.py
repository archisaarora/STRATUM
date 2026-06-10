"""Stage 5.1 — construct the fine-tuning dataset for procurement classification.

Inputs: a contracts CSV (export of feature_contracts_merged from Foundry,
or local-data/raw_usaspending_contracts.csv from scripts/local_fetch.py).

Labeling strategy per the build spec:
  1. Seed labels — NAICS/PSC codes that map cleanly to capability domains
     (reference-data/ref_naics_domain_mapping.csv), high confidence.
  2. Keyword bootstrapping — weak labels from the deterministic keyword
     classifier for additional coverage.

Output: instruction-tuning JSONL (80/10/10 stratified by primary domain):
  {"instruction": ..., "input": "", "output": "<json classification>"}

Usage:
    python build_training_data.py --contracts contracts.csv --out data/
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "transforms-python" / "src"))

from stratum.core.llm.keyword_classifier import (  # noqa: E402
    build_naics_psc_lookup, classify)
from stratum.core.llm.prompts import build_prompt  # noqa: E402

SEED_TARGET = 5_000
BOOTSTRAP_TARGET = 20_000


def label_contracts(df: pd.DataFrame, naics_lookup: dict) -> list[dict]:
    examples = []
    seed_count = boot_count = 0
    for row in df.itertuples(index=False):
        desc = getattr(row, "description_raw_text", None) or \
            getattr(row, "award_description", None)
        if not isinstance(desc, str) or len(desc) < 60:
            continue
        naics = str(getattr(row, "naics_code", "") or "")
        psc = str(getattr(row, "psc_code", "") or
                  getattr(row, "product_or_service_code", "") or "")
        has_seed_code = naics in naics_lookup or psc in naics_lookup

        result = classify(desc, naics_code=naics, psc_code=psc,
                          naics_psc_lookup=naics_lookup)
        if result["capability_domains"] == ["none"] and not has_seed_code:
            # keep a slice of negatives so the model learns "none"
            if random.random() > 0.05:
                continue
        if has_seed_code and seed_count < SEED_TARGET:
            source, confidence = "seed_naics_psc", "high"
            seed_count += 1
        elif boot_count < BOOTSTRAP_TARGET:
            source, confidence = "keyword_bootstrap", "weak"
            boot_count += 1
        else:
            continue

        target = {
            "capability_domains": result["capability_domains"],
            "technology_keywords": result["technology_keywords"],
            "threat_relevance_score": result["threat_relevance_score"],
            "capability_maturity_stage": result["capability_maturity_stage"],
            "reasoning": result["reasoning"],
        }
        prompt = build_prompt(
            desc,
            getattr(row, "awarding_agency", None)
            or getattr(row, "awarding_agency_name", None),
            getattr(row, "recipient_name", None),
            getattr(row, "total_value_usd", None)
            or getattr(row, "total_obligated_amount", None),
        )
        examples.append({
            "instruction": prompt,
            "input": "",
            "output": json.dumps(target),
            "primary_domain": target["capability_domains"][0],
            "label_source": source,
            "label_confidence": confidence,
        })
    print(f"labeled {len(examples)} examples "
          f"({seed_count} seed, {boot_count} bootstrap)")
    return examples


def stratified_split(examples: list[dict], seed: int = 17):
    random.seed(seed)
    by_domain = defaultdict(list)
    for ex in examples:
        by_domain[ex["primary_domain"]].append(ex)
    train, val, test = [], [], []
    for domain, items in by_domain.items():
        random.shuffle(items)
        n = len(items)
        n_val, n_test = max(1, n // 10), max(1, n // 10)
        val.extend(items[:n_val])
        test.extend(items[n_val:n_val + n_test])
        train.extend(items[n_val + n_test:])
    for split in (train, val, test):
        random.shuffle(split)
    return train, val, test


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--contracts", required=True, help="contracts CSV path")
    p.add_argument("--out", default="data", help="output directory")
    args = p.parse_args()

    df = pd.read_csv(args.contracts)
    naics_lookup = build_naics_psc_lookup(
        pd.read_csv(REPO / "reference-data" / "ref_naics_domain_mapping.csv"))
    examples = label_contracts(df, naics_lookup)
    train, val, test = stratified_split(examples)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, split in [("train", train), ("val", val), ("test", test)]:
        path = out / f"{name}.jsonl"
        with path.open("w") as f:
            for ex in split:
                f.write(json.dumps(ex) + "\n")
        print(f"  {name}: {len(split)} -> {path}")


if __name__ == "__main__":
    main()
