"""Stage 5.3 — evaluate the fine-tuned model on the held-out test split.

Metrics (per the build spec):
  * per-domain F1 (multi-label) — deployment gate: >0.78 on every domain
  * threat_relevance_score MAE
  * capability_maturity_stage accuracy (5-class)

Works against any OpenAI-compatible endpoint (the served GGUF model):
    python evaluate.py --data data/test.jsonl \
        --endpoint http://localhost:8000/v1 --model stratum-mistral-7b-procurement

Writes evaluation_results.csv — upload to Foundry as model_evaluation_results.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "transforms-python" / "src"))

from stratum.core.llm.json_guard import (  # noqa: E402
    InvalidClassification, parse_classification)
from stratum.core.llm.taxonomy import CAPABILITY_DOMAINS  # noqa: E402


def call_endpoint(endpoint: str, model: str, prompt: str) -> str:
    resp = requests.post(
        f"{endpoint}/chat/completions",
        json={"model": model, "temperature": 0.0, "max_tokens": 700,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--endpoint", default="http://localhost:8000/v1")
    p.add_argument("--model", default="stratum-mistral-7b-procurement")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    rows = [json.loads(line) for line in Path(args.data).read_text().splitlines()
            if line][: args.limit]
    tp = defaultdict(int); fp = defaultdict(int); fn = defaultdict(int)
    relevance_errors, stage_hits, parse_failures = [], [], 0

    for i, ex in enumerate(rows):
        truth = json.loads(ex["output"])
        try:
            pred = parse_classification(
                call_endpoint(args.endpoint, args.model, ex["instruction"]))
        except (InvalidClassification, requests.RequestException):
            parse_failures += 1
            continue
        t = set(truth["capability_domains"]) - {"none"}
        q = set(pred["capability_domains"])
        for d in q & t:
            tp[d] += 1
        for d in q - t:
            fp[d] += 1
        for d in t - q:
            fn[d] += 1
        relevance_errors.append(
            abs(pred["threat_relevance_score"] - truth["threat_relevance_score"]))
        stage_hits.append(
            pred["capability_maturity_stage"] == truth["capability_maturity_stage"])
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(rows)}")

    results = []
    for d in CAPABILITY_DOMAINS:
        if d == "none" or (tp[d] + fp[d] + fn[d]) == 0:
            continue
        precision = tp[d] / (tp[d] + fp[d]) if (tp[d] + fp[d]) else 0.0
        recall = tp[d] / (tp[d] + fn[d]) if (tp[d] + fn[d]) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        results.append({"metric": f"f1.{d}", "value": round(f1, 4),
                        "support": tp[d] + fn[d]})
    mae = sum(relevance_errors) / len(relevance_errors) if relevance_errors else None
    results.append({"metric": "threat_relevance_mae",
                    "value": round(mae, 4) if mae is not None else None,
                    "support": len(relevance_errors)})
    results.append({"metric": "maturity_stage_accuracy",
                    "value": round(sum(stage_hits) / len(stage_hits), 4)
                    if stage_hits else None, "support": len(stage_hits)})
    results.append({"metric": "json_parse_failure_rate",
                    "value": round(parse_failures / len(rows), 4),
                    "support": len(rows)})

    df = pd.DataFrame(results)
    df.to_csv("evaluation_results.csv", index=False)
    print(df.to_string(index=False))
    f1s = df[df["metric"].str.startswith("f1.")]["value"]
    gate = bool(len(f1s)) and f1s.min() > 0.78
    print(f"\nDEPLOYMENT GATE (all F1 > 0.78): {'PASS' if gate else 'FAIL'}")


if __name__ == "__main__":
    main()
