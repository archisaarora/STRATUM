"""Stage 5.2 — QLoRA fine-tune of Mistral-7B-Instruct-v0.3 for procurement
classification.

Run on a CUDA machine (single 24GB GPU is enough at 4-bit) or Colab:
    pip install transformers peft trl bitsandbytes datasets accelerate torch
    python train_mistral_procurement.py --data data/ --out mistral-stratum-procurement

After training, export for CPU inference (llama.cpp):
    python -m peft merge ...  # or use merge_and_export() below
    ./llama.cpp/convert_hf_to_gguf.py merged/ --outfile stratum-mistral.gguf \
        --outtype q4_k_m
Serve with an OpenAI-compatible endpoint for LLM_MODE="external":
    python -m llama_cpp.server --model stratum-mistral.gguf --chat_format mistral-instruct
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"


def load_split(path: Path):
    from datasets import Dataset

    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    # Mistral instruct chat format; output is the JSON classification.
    texts = [
        f"<s>[INST] {r['instruction']} [/INST] {r['output']}</s>"
        for r in rows
    ]
    return Dataset.from_dict({"text": texts})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data")
    p.add_argument("--out", default="./mistral-stratum-procurement")
    p.add_argument("--epochs", type=int, default=3)
    args = p.parse_args()

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig, TrainingArguments)
    from trl import SFTTrainer

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb_config, device_map="auto")
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    data_dir = Path(args.data)
    training_args = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_steps=100,
        learning_rate=2e-4,
        bf16=torch.cuda.is_available(),
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch",
        load_best_model_at_end=True,
        report_to="none",
    )
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=load_split(data_dir / "train.jsonl"),
        eval_dataset=load_split(data_dir / "val.jsonl"),
    )
    trainer.train()
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"LoRA adapter saved to {args.out}. "
          f"Run evaluate.py before deploying (gate: F1 > 0.78 on validation).")


def merge_and_export(adapter_dir: str, out_dir: str = "merged") -> None:
    """Merge the LoRA adapter into the base model for GGUF conversion."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float16)
    merged = PeftModel.from_pretrained(base, adapter_dir).merge_and_unload()
    merged.save_pretrained(out_dir)
    AutoTokenizer.from_pretrained(MODEL_ID).save_pretrained(out_dir)


if __name__ == "__main__":
    main()
