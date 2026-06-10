# STRATUM model training — Mistral-7B procurement classifier (Stage 5)

Fine-tunes `mistralai/Mistral-7B-Instruct-v0.3` with QLoRA (4-bit) to beat
zero-shot prompting on the 18-domain procurement taxonomy. Runs **outside
Foundry** (any single 24 GB CUDA GPU, or Colab); the result serves the
pipeline's `LLM_MODE = "external"` path.

## Workflow

```bash
pip install pandas transformers peft trl bitsandbytes datasets accelerate torch

# 1. Build instruction data from real contracts
#    (export feature_contracts_merged from Foundry as CSV, or use
#     local-data/raw_usaspending_contracts.csv from scripts/local_fetch.py)
python build_training_data.py --contracts contracts.csv --out data/
#    -> data/train.jsonl / val.jsonl / test.jsonl  (80/10/10, stratified,
#       seed labels from NAICS/PSC + keyword-bootstrapped weak labels)

# 2. Train (QLoRA: r=16, alpha=32, q/k/v/o projections, 3 epochs, lr 2e-4)
python train_mistral_procurement.py --data data/ --out mistral-stratum-procurement

# 3. Merge + convert to GGUF for CPU inference
python -c "from train_mistral_procurement import merge_and_export; \
           merge_and_export('mistral-stratum-procurement')"
./llama.cpp/convert_hf_to_gguf.py merged/ --outfile stratum-mistral.gguf --outtype q4_k_m

# 4. Serve OpenAI-compatible
pip install 'llama-cpp-python[server]'
python -m llama_cpp.server --model stratum-mistral.gguf \
       --chat_format mistral-instruct --port 8000

# 5. Evaluate against the served endpoint — deployment gate: F1 > 0.78
python evaluate.py --data data/test.jsonl --endpoint http://localhost:8000/v1
# -> evaluation_results.csv  (upload to Foundry as model_evaluation_results)
```

## Wiring into Foundry

1. Host the endpoint somewhere Foundry can egress to.
2. Create a REST source for it (runbook §4a), paste the RID into
   `MISTRAL_SOURCE_RID` in
   `transforms-python/src/stratum/datasets/features/llm_classified.py`.
3. Set `LLM_MODE = "external"` in `stratum/config.py`, commit, rebuild.

Because training prompts come from the same `build_prompt()` used at
inference, train and serve distributions match exactly.
