"""
Inferencia local del modelo AURA (CPU por defecto).

Uso:
    python training/scripts/infer_local.py --prompt "Hola"
    python training/scripts/infer_local.py --prompt "Hola" --stream
    python training/scripts/infer_local.py --compare
"""

from __future__ import annotations

import argparse
import logging
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("infer_local")

ROOT = Path(__file__).resolve().parents[2]
LORA_DIR = ROOT / "fine-tuned-ame" / "aura_finetuned_lora"
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


@lru_cache(maxsize=1)
def get_engine():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_path = str(LORA_DIR) if LORA_DIR.exists() else BASE_MODEL
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype=torch.float32,
        device_map="cpu",
        low_cpu_mem_usage=True,
    )
    model.eval()
    return {"model": model, "tokenizer": tokenizer}


def infer(prompt: str, stream: bool = False) -> dict:
    engine = get_engine()
    model = engine["model"]
    tokenizer = engine["tokenizer"]

    messages = [{"role": "user", "content": prompt}]
    try:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    except Exception:
        text = f"User: {prompt}\nAssistant:"

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)

    start = time.time()
    if stream:
        from transformers import TextStreamer

        streamer = TextStreamer(tokenizer, skip_prompt=True)
        with streamer:
            outputs = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=tokenizer.pad_token_id,
            )
        latency = (time.time() - start) * 1000
        response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        tokens = len(outputs[0]) - inputs["input_ids"].shape[1]
        return {"text": response.strip(), "latency_ms": round(latency, 2), "tokens": tokens}
    else:
        outputs = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id,
        )
        latency = (time.time() - start) * 1000
        response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        tokens = len(outputs[0]) - inputs["input_ids"].shape[1]
        tps = tokens / (latency / 1000) if latency > 0 else 0.0
        return {"text": response.strip(), "latency_ms": round(latency, 2), "tokens": tokens, "tokens_per_sec": round(tps, 2)}


def compare(prompt: str) -> None:
    base = infer(prompt)
    print(f"[BASE] {base['text'][:120]} | {base['latency_ms']:.1f}ms | {base.get('tokens_per_sec', 0):.1f} t/s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inferencia local AURA")
    parser.add_argument("--prompt", required=True, help="Prompt de entrada")
    parser.add_argument("--stream", action="store_true", help="Streaming de tokens")
    parser.add_argument("--compare", action="store_true", help="Comparar con base")
    args = parser.parse_args()

    if args.compare:
        compare(args.prompt)
        return 0

    res = infer(args.prompt, stream=args.stream)
    print(res["text"])
    logger.info("latency=%.1fms tokens=%d tps=%.1f", res["latency_ms"], res["tokens"], res.get("tokens_per_sec", 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())