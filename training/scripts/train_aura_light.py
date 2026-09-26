"""
Lightweight CPU-friendly QLoRA fine-tuning for AURA small model.

Optimized for:
- Qwen/Qwen2.5-0.5B-Instruct on CPU
- Short sequences (max_seq=256) to keep CPU time low
- Small LoRA rank (r=4)
- Minimal epochs (1-2)
- No 4-bit on CPU (use standard LoRA with torch.float32)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_aura_light")

from datasets import Dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    TrainingArguments,
    Trainer,
)
import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight CPU QLoRA trainer")
    parser.add_argument("--model-name", default=os.getenv("AURA_TRAINING_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct"))
    parser.add_argument("--dataset-path", default=os.getenv("AURA_TRAINING_DATASET_PATH", "training/data/continual_dataset.jsonl"))
    parser.add_argument("--output-dir", default=os.getenv("AURA_TRAINING_OUTPUT_DIR", "fine-tuned-ame"))
    parser.add_argument("--max-seq-length", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=4)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--warmup-steps", type=int, default=3)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument("--max-samples", type=int, default=500)
    return parser.parse_args()


def load_jsonl(path: str, max_samples: int = 500) -> List[Dict[str, str]]:
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = obj.get("text") or obj.get("prompt")
            output = obj.get("output") or obj.get("response")
            if text and output:
                samples.append({"text": text, "output": output})
                if len(samples) >= max_samples:
                    break
    return samples


def format_pair(sample: Dict[str, str], tokenizer) -> str:
    messages = [
        {"role": "user", "content": sample["text"]},
        {"role": "assistant", "content": sample["output"]},
    ]
    try:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    except Exception:
        return f"User: {sample['text']}\nAssistant: {sample['output']}"


def main() -> int:
    args = parse_args()
    torch.manual_seed(args.seed)

    logger.info("Loading tokenizer: %s", args.model_name)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info("Loading model: %s on CPU", args.model_name)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        trust_remote_code=True,
        torch_dtype=torch.float32,
        device_map="cpu",
        low_cpu_mem_usage=True,
    )

    logger.info("Applying LoRA r=%d", args.lora_r)
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    logger.info("Loading dataset: %s", args.dataset_path)
    samples = load_jsonl(args.dataset_path, max_samples=args.max_samples)
    if not samples:
        logger.info("No data found. Exiting.")
        return 1

    texts = [format_pair(s, tokenizer) for s in samples]
    tokenized = tokenizer(texts, truncation=True, max_length=args.max_seq_length, padding=False)
    dataset = Dataset.from_dict({"input_ids": tokenized["input_ids"], "attention_mask": tokenized["attention_mask"]})

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(out_dir / "outputs"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.lr,
        warmup_steps=args.warmup_steps,
        lr_scheduler_type="linear",
        seed=args.seed,
        logging_steps=1,
        report_to="none",
        remove_unused_columns=False,
        dataloader_pin_memory=False,
        fp16=False,
        bf16=False,
    )

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
    )

    logger.info("Starting training...")
    start = time.time()
    trainer.train()
    elapsed = time.time() - start
    logger.info("Training complete in %.1fs", elapsed)

    lora_path = out_dir / "aura_finetuned_lora"
    model.save_pretrained(str(lora_path))
    tokenizer.save_pretrained(str(lora_path))
    logger.info("LoRA adapters saved -> %s", lora_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
