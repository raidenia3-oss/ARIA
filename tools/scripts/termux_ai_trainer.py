#!/usr/bin/env python3
"""
AURA Termux AI Trainer — Módulo de entrenamiento on-device para Android (Termux).

Diseñado para hardware móvil limitado:
  - CPU-only (sin GPU)
  - Memoria RAM reducida (~4-8 GB)
  - Almacenamiento limitado

 usa LoRA (Low-Rank Adaptation) + cuantización 4-bit para entrenar
 modelos pequeños sin agotar recursos.

Deployment: SCP a Termux → python termux_ai_trainer.py
   ssh u0_a252@192.168.18.21 -p 8022
   scp -P 8022 termux_ai_trainer.py ~/.local/share/ame/

Modelos compatibles (peso aproximado):
  Qwen2.5-0.5B   (~500 MB)  · más ligero
  TinyLlama-1.1B (~2 GB)     · más capacidad
"""

from __future__ import annotations

import json
import os
import sys
import logging
import argparse
import time
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("TermuxAI")

MOBILE_MODELS: Dict[str, Dict] = {
    "qwen-0.5b": {
        "hf_id": "Qwen/Qwen2.5-0.5B",
        "size_mb": 500,
        "params": "0.5B",
        "trust": True,
    },
    "tinyllama-1.1b": {
        "hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "size_mb": 2000,
        "params": "1.1B",
        "trust": False,
    },
    "gemma-2b": {
        "hf_id": "google/gemma-2b-it",
        "size_mb": 5000,
        "params": "2B",
        "trust": True,
    },
}

DEFAULT_OUTPUT_DIR = Path.home() / ".local" / "share" / "ame" / "trained"


class SystemResources:
    """Inspecciona recursos del dispositivo Termux."""

    @staticmethod
    def ram_info() -> Dict[str, float]:
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_pct": mem.percent,
            }
        except ImportError:
            try:
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                    total = int(lines[0].split()[1]) / (1024**2)
                    avail = int(lines[2].split()[1]) / (1024**2)
                return {
                    "total_gb": round(total, 2),
                    "available_gb": round(avail, 2),
                    "used_pct": round(((total - avail) / total) * 100, 1),
                }
            except Exception:
                return {"total_gb": 0, "available_gb": 0, "used_pct": 0}

    @staticmethod
    def cpu_info() -> Dict:
        try:
            import psutil
            return {"cores": psutil.cpu_count(logical=True)}
        except Exception:
            return {"cores": 1}

    @staticmethod
    def disk_info(path: str = ".") -> Dict[str, float]:
        try:
            stat = os.statvfs(path)
            free_gb = (stat.f_frsize * stat.f_bavail) / (1024**3)
            total_gb = (stat.f_frsize * stat.f_blocks) / (1024**3)
            return {"free_gb": round(free_gb, 2), "total_gb": round(total_gb, 2)}
        except Exception:
            return {"free_gb": 0, "total_gb": 0}


class TermuxTrainer:
    """
    Entrenador ligero para fine-tuning on-device con LoRA.

    Estrategia de ahorro de memoria:
      1. Cuantización 4-bit (NF4) — reduce VRAM/RAM ~4x
      2. LoRA rank-8 — solo ~0.1% de parámetros entrenables
      3. gradient_checkpointing — reduce memoria de activaciones
      4. batch_size=1 + gradient_accumulation=4
    """

    def __init__(
        self,
        model_key: str = "qwen-0.5b",
        output_dir: str = str(DEFAULT_OUTPUT_DIR),
        use_lora: bool = True,
    ):
        self.model_key = model_key
        self.model_spec = MOBILE_MODELS.get(model_key, MOBILE_MODELS["qwen-0.5b"])
        self.model_id = self.model_spec["hf_id"]
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_lora = use_lora
        self.tokenizer: Optional[object] = None
        self.model: Optional[object] = None
        self.device = "cpu"

    def diagnose(self) -> Dict:
        """Reporta recursos del sistema y modelo objetivo."""
        ram = SystemResources.ram_info()
        cpu = SystemResources.cpu_info()
        disk = SystemResources.disk_info(str(self.output_dir))
        model_mb = self.model_spec["size_mb"]

        return {
            "model_key": self.model_key,
            "model_id": self.model_id,
            "model_size_mb": model_mb,
            "ram": ram,
            "cpu": cpu,
            "disk": disk,
            "device": "cpu",
            "recommendation": self._recommend(ram, disk, model_mb),
        }

    def _recommend(self, ram: Dict, disk: Dict, model_mb: int) -> str:
        avail = ram["available_gb"]
        free_disk = disk["free_gb"]
        if avail < 2.0 or free_disk < model_mb / 1024 + 1:
            return "Riesgo alto — usa qwen-0.5b + LoRA + 4-bit"
        if avail < 4.0:
            return "Usable con LoRA + 4-bit"
        return "OK para fine-tuning completo"

    # ------------------------------------------------------------------ #
    #  Dependencias
    # ------------------------------------------------------------------ #
    def check_deps(self) -> Tuple[bool, List[str]]:
        """Verifica que los paquetes requeridos están instalados."""
        required = ["torch", "transformers", "datasets", "peft"]
        missing = []
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        if not missing:
            try:
                import bitsandbytes  # noqa: F401
            except ImportError:
                missing.append("bitsandbytes")
        return (len(missing) == 0), missing

    def install_deps(self) -> None:
        """Instala dependencias vía pip (CPU-only wheels)."""
        pkgs = [
            "torch",
            "transformers",
            "datasets",
            "peft",
            "accelerate",
            "bitsandbytes",
            "psutil",
        ]
        logger.info(f"Instalando dependencias en Termux: {', '.join(pkgs)}")
        for pkg in pkgs:
            logger.info(f"  → pip install {pkg}")
            ret = os.system(f"{sys.executable} -m pip install {pkg}")
            if ret != 0:
                logger.warning(f"  Falló instalación de {pkg} (puede necesitar build tools)")

    # ------------------------------------------------------------------ #
    #  Carga del modelo
    # ------------------------------------------------------------------ #
    def download_model(self, hf_token: Optional[str] = None) -> str:
        """
        Descarga el modelo base desde HuggingFace a caché local.
        Se debe ejecutar antes de load_model() si no está cacheado.
        """
        from huggingface_hub import snapshot_download

        token = hf_token or os.getenv("HF_TOKEN", "")
        logger.info(f"Downloading model: {self.model_id}")
        local_path = snapshot_download(
            self.model_id,
            token=token if token else None,
            local_files_only=False,
        )
        logger.info(f"Model cached at: {local_path}")
        return local_path

    def load_model(self, model_path: Optional[str] = None) -> bool:
        """Carga el modelo con cuantización 4-bit y LoRA."""
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        import torch

        model_src = model_path or self.model_id
        logger.info(f"Loading model: {model_src} (CPU, 4-bit)")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_src,
            trust_remote_code=self.model_spec.get("trust", False),
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_src,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=self.model_spec.get("trust", False),
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
        except Exception as e:
            logger.warning(f"4-bit load failed ({e}), retrying sin cuantización...")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_src,
                device_map="auto",
                trust_remote_code=self.model_spec.get("trust", False),
                torch_dtype=torch.float32,
            )

        if self.use_lora:
            from peft import LoraConfig, get_peft_model, TaskType

            lora_cfg = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=8,
                lora_alpha=32,
                lora_dropout=0.1,
                target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
                if "qwen" in self.model_key.lower() or "gemma" in self.model_key.lower()
                else ["q_proj", "v_proj"],
                bias="none",
            )
            self.model = get_peft_model(self.model, lora_cfg)
            info = self.model.print_trainable_parameters()
            logger.info(f"LoRA aplicado — parámetros entrenables reducidos")

        # Activar gradient checkpointing para ahorrar memoria
        if hasattr(self.model, "gradient_checkpointing_enable"):
            try:
                self.model.gradient_checkpointging_enable()
            except Exception:
                pass

        logger.info("Model loaded successfully")
        return True

    # ------------------------------------------------------------------ #
    #  Datos
    # ------------------------------------------------------------------ #
    def prepare_data(
        self, data_path: str, max_length: int = 512
    ) -> Tuple[List[str], List[str]]:
        """Carga y particiona datos JSONL en train/eval."""
        texts: List[str] = []
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    text = entry.get("text", "")
                    output = entry.get("output", "")
                    if text and output:
                        texts.append(f"User: {text}\nAssistant: {output}\n")
                except json.JSONDecodeError:
                    continue

        if not texts:
            logger.error(f"No valid conversations found in {data_path}")
            return [], []

        split = int(len(texts) * 0.8)
        logger.info(f"Data: {len(texts)} total → {split} train, {len(texts) - split} eval")
        return texts[:split], texts[split:]

    # ------------------------------------------------------------------ #
    #  Entrenamiento
    # ------------------------------------------------------------------ #
    def train(
        self,
        data_path: str,
        epochs: int = 1,
        lr: float = 5e-5,
        max_length: int = 512,
    ) -> str:
        """Fine-tune el modelo on-device."""
        if self.model is None or self.tokenizer is None:
            logger.error("Model not loaded. Call load_model() first.")
            return ""

        from datasets import Dataset
        from transformers import (
            TrainingArguments,
            Trainer,
            DataCollatorForLanguageModeling,
        )

        train_texts, eval_texts = self.prepare_data(data_path, max_length)
        if not train_texts:
            return ""

        train_enc = self.tokenizer(
            train_texts, truncation=True, max_length=max_length, padding="max_length"
        )
        eval_enc = self.tokenizer(
            eval_texts if eval_texts else train_texts[:5],
            truncation=True,
            max_length=max_length,
            padding="max_length",
        )

        train_ds = Dataset.from_dict({
            "input_ids": train_enc["input_ids"],
            "attention_mask": train_enc["attention_mask"],
        })
        eval_ds = Dataset.from_dict({
            "input_ids": eval_enc["input_ids"],
            "attention_mask": eval_enc["attention_mask"],
        })

        run_name = f"termux-{self.model_key}-{int(time.time())}"
        output_path = self.output_dir / run_name
        output_path.mkdir(parents=True, exist_ok=True)

        training_args = TrainingArguments(
            output_dir=str(output_path),
            num_train_epochs=epochs,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=4,
            learning_rate=lr,
            fp16=False,
            bf16=False,
            logging_steps=5,
            eval_strategy="steps",
            eval_steps=50,
            save_steps=100,
            save_total_limit=1,
            report_to="none",
            remove_unused_columns=False,
            dataloader_pin_memory=False,
            warmup_steps=5,
            torch_compile=False,
        )

        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer, mlm=False
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=eval_ds,
            data_collator=data_collator,
        )

        logger.info(f"Starting training: {epochs} epoch(s), {len(train_texts)} samples")
        start = time.time()
        trainer.train()
        elapsed = time.time() - start
        logger.info(f"Training complete in {elapsed:.1f}s")

        self._save(output_path)
        return str(output_path)

    def _save(self, save_path: Path) -> None:
        """Guarda modelo, tokenizer y metadata."""
        self.model.save_pretrained(save_path)
        self.tokenizer.save_pretrained(save_path)

        config = {
            "base_model": self.model_id,
            "fine_tuning_method": "LoRA" if self.use_lora else "full",
            "device": "cpu",
            "quantization": "4-bit" if self._has_quant() else "fp32",
            "params": self.model_spec["params"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        with open(save_path / "training_config.json", "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Model saved to: {save_path}")

    def _has_quant(self) -> bool:
        try:
            import torch
            for p in self.model.parameters():
                if p.dtype in (torch.float16, torch.bfloat16):
                    return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    #  Inferencia
    # ------------------------------------------------------------------ #
    def infer(self, prompt: str, max_new_tokens: int = 128) -> str:
        """Genera respuesta con el modelo cargado."""
        if self.model is None or self.tokenizer is None:
            return "[ERROR] Model not loaded"

        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=512
        )
        import torch
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                do_sample=True,
                use_cache=False,
            )
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    # ------------------------------------------------------------------ #
    #  Sync con PC (opcional)
    # ------------------------------------------------------------------ #
    def sync_to_pc(
        self,
        model_dir: str,
        pc_host: str = "192.168.18.21",
        pc_port: int = 8022,
        pc_user: str = "u0_a252",
    ) -> bool:
        """
        Opcional: envía el modelo entrenado a la PC vía SSH.
        Requiere key SSH configurada (~/.ssh/id_rsa.pub → PC authorized_keys).
        """
        target = f"{pc_user}@{pc_host}"
        remote_path = "~/ame-trained-models/"
        cmd = (
            f"ssh -p {pc_port} -o StrictHostKeyChecking=accept-new "
            f"{target} 'mkdir -p {remote_path}' && "
            f"scp -P {pc_port} -r {model_dir} {target}:{remote_path}"
        )
        logger.info(f"Syncing {model_dir} → {target}:{remote_path}")
        ret = os.system(cmd)
        if ret == 0:
            logger.info("Sync complete")
            return True
        logger.error("Sync failed — verifica conectividad SSH")
        return False


# ---------------------------------------------------------------------- #
#  CLI
# ---------------------------------------------------------------------- #
def cmd_diagnose(args: argparse.Namespace) -> None:
    t = TermuxTrainer(model_key=args.model)
    diag = t.diagnose()
    print(json.dumps(diag, indent=2, ensure_ascii=False))


def cmd_install(args: argparse.Namespace) -> None:
    t = TermuxTrainer(model_key=args.model)
    t.install_deps()


def cmd_download(args: argparse.Namespace) -> None:
    t = TermuxTrainer(model_key=args.model)
    t.download_model(hf_token=args.hf_token)


def cmd_train(args: argparse.Namespace) -> None:
    t = TermuxTrainer(
        model_key=args.model,
        output_dir=args.output,
        use_lora=not args.no_lora,
    )

    ok, missing = t.check_deps()
    if not ok:
        logger.info(f"Instalando dependencias faltantes: {', '.join(missing)}")
        t.install_deps()
        ok, missing = t.check_deps()
        if not ok:
            logger.error(f"Dependencies still missing: {missing}")
            sys.exit(1)

    diag = t.diagnose()
    print(json.dumps(diag, indent=2, ensure_ascii=False))

    if not t.load_model(args.model_path):
        logger.error("Failed to load model")
        sys.exit(1)

    out = t.train(
        data_path=args.data,
        epochs=args.epochs,
        lr=args.lr,
        max_length=args.max_length,
    )
    print(f"\n[OK] Modelo entrenado: {out}")

    if args.sync_pc:
        t.sync_to_pc(out, pc_host=args.pc_host, pc_port=args.pc_port, pc_user=args.pc_user)


def cmd_infer(args: argparse.Namespace) -> None:
    t = TermuxTrainer(model_key=args.model, output_dir=args.output)
    if args.model_path:
        if not t.load_model(args.model_path):
            logger.error("Failed to load model")
            sys.exit(1)
    else:
        if not t.load_model():
            logger.error("Failed to load model")
            sys.exit(1)
    result = t.infer(args.prompt, max_new_tokens=args.max_tokens)
    print(result)


def main():
    p = argparse.ArgumentParser(
        prog="termux-ai-trainer",
        description="AURA Termux AI Trainer — fine-tuning on-device",
    )
    p.add_argument(
        "--model",
        default="qwen-0.5b",
        choices=list(MOBILE_MODELS.keys()),
        help="Modelo base a usar",
    )
    p.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Directorio de salida")
    p.add_argument("--data", default="training-data.jsonl", help="Archivo JSONL de entrenamiento")
    p.add_argument("--hf-token", default=None, help="Token de HuggingFace (o usar HF_TOKEN env)")

    sub = p.add_subparsers(dest="command", help="Comando a ejecutar")

    s_diag = sub.add_parser("diagnose", help="Diagnosticar recursos del dispositivo")
    s_diag.set_defaults(func=cmd_diagnose)

    s_inst = sub.add_parser("install", help="Instalar dependencias Python")
    s_inst.set_defaults(func=cmd_install)

    s_dl = sub.add_parser("download", help="Descargar modelo base a caché")
    s_dl.set_defaults(func=cmd_download)
    s_dl.add_argument("--hf-token", default=None)

    s_tr = sub.add_parser("train", help="Entrenar modelo on-device")
    s_tr.add_argument("--epochs", type=int, default=1)
    s_tr.add_argument("--lr", type=float, default=5e-5)
    s_tr.add_argument("--max-length", type=int, default=512)
    s_tr.add_argument("--no-lora", action="store_true", help="Deshabilitar LoRA (full fine-tune)")
    s_tr.add_argument("--model-path", default=None, help="Ruta local del modelo")
    s_tr.add_argument("--sync-pc", action="store_true", help="Sincronizar modelo entrenado a PC")
    s_tr.add_argument("--pc-host", default="192.168.18.21")
    s_tr.add_argument("--pc-port", type=int, default=8022)
    s_tr.add_argument("--pc-user", default="u0_a252")
    s_tr.set_defaults(func=cmd_train)

    s_inf = sub.add_parser("infer", help="Generar texto con modelo entrenado")
    s_inf.add_argument("--prompt", required=True, help="Prompt de entrada")
    s_inf.add_argument("--model-path", default=None, help="Ruta local del modelo")
    s_inf.add_argument("--max-tokens", type=int, default=128)
    s_inf.set_defaults(func=cmd_infer)

    args = p.parse_args()

    if not args.command:
        p.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
