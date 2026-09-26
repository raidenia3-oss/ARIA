#!/usr/bin/env python3
"""
AURA PC Model Downloader & Training Environment Setup.

Descarga un modelo de IA ligero y potente, configura un entorno virtual
de entrenamiento y prepara los datos.

Modelos recomendados (ligero + potente):
  qwen-1.5b   (~1.0 GB)  · balance óptimo rendimiento/recursos
  gemma-2b    (~5.0 GB)  · eficiente de Google
  phi3-mini   (~2.0 GB)  · 3.8B params, muy eficiente
  qwen-3b     (~2.0 GB)  · versión más potente de Qwen2.5
  tinyllama   (~2.0 GB)  · Llama miniaturizada

Uso:
  python scripts/setup_pc_training.py                    # setup completo
  python scripts/setup_pc_training.py --model qwen-1.5b  # modelo específico
  python scripts/setup_pc_training.py --download-only    # solo descargar modelo
  python scripts/setup_pc_training.py --list-models    # listar modelos disponibles
"""

from __future__ import annotations

import os
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("AURA_ModelSetup")

PC_MODELS: Dict[str, Dict] = {
    "qwen-0.5b": {
        "hf_id": "Qwen/Qwen2.5-0.5B",
        "size_mb": 500,
        "params": "0.5B",
        "requires_gpu": False,
        "trust_remote_code": True,
    },
    "qwen-1.5b": {
        "hf_id": "Qwen/Qwen2.5-1.5B",
        "size_mb": 1000,
        "params": "1.5B",
        "requires_gpu": False,
        "trust_remote_code": True,
    },
    "qwen-3b": {
        "hf_id": "Qwen/Qwen2.5-3B",
        "size_mb": 2000,
        "params": "3B",
        "requires_gpu": False,
        "trust_remote_code": True,
    },
    "gemma-2b": {
        "hf_id": "google/gemma-2b-it",
        "size_mb": 5000,
        "params": "2B",
        "requires_gpu": False,
        "trust_remote_code": True,
    },
    "phi3-mini": {
        "hf_id": "microsoft/Phi-3-mini-4k-instruct",
        "size_mb": 2000,
        "params": "3.8B",
        "requires_gpu": False,
        "trust_remote_code": False,
    },
    "tinyllama": {
        "hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "size_mb": 2000,
        "params": "1.1B",
        "requires_gpu": False,
        "trust_remote_code": False,
    },
}

PC_TRAINING_DEPS: List[str] = [
    "torch>=2.1.0",
    "transformers>=4.40.0",
    "peft>=0.10.0",
    "datasets>=2.19.0",
    "accelerate>=0.30.0",
    "bitsandbytes>=0.43.0",
    "huggingface-hub>=0.23.0",
    "scikit-learn>=1.4.0",
    "numpy>=1.26.0",
]


class PCPreSetup:
    """Configuración del entorno de entrenamiento en PC."""

    def __init__(
        self,
        model_key: str = "qwen-1.5b",
        venv_dir: str = "venv-training",
        model_cache_dir: str = "models",
        hf_token: Optional[str] = None,
    ):
        self.model_key = model_key
        self.model_spec = PC_MODELS.get(model_key, PC_MODELS["qwen-1.5b"])
        self.model_id = self.model_spec["hf_id"]
        self.venv_dir = Path(venv_dir)
        self.model_cache_dir = Path(model_cache_dir)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self.hf_token = hf_token or os.getenv("HF_TOKEN", "")
        self.repo_root = Path(__file__).resolve().parent.parent

    # ------------------------------------------------------------------ #
    #  Diagnóstico del PC
    # ------------------------------------------------------------------ #
    def diagnose_pc(self) -> Dict:
        """Reporta recursos del PC."""
        import platform

        info: Dict = {
            "platform": platform.platform(),
            "python": sys.version,
            "model_key": self.model_key,
            "model_id": self.model_id,
            "model_size_mb": self.model_spec["size_mb"],
            "params": self.model_spec["params"],
            "requires_gpu": self.model_spec["requires_gpu"],
        }

        try:
            import torch
            info["cuda_available"] = torch.cuda.is_available()
            info["cuda_devices"] = torch.cuda.device_count() if torch.cuda.is_available() else 0
        except ImportError:
            info["cuda_available"] = False
            info["cuda_devices"] = 0

        try:
            import psutil
            ram = psutil.virtual_memory()
            info["ram_total_gb"] = round(ram.total / (1024**3), 2)
            info["ram_available_gb"] = round(ram.available / (1024**3), 2)
            cpu_count = psutil.cpu_count(logical=True)
            info["cpu_cores"] = cpu_count
        except ImportError:
            pass

        disk = shutil.disk_usage(str(self.repo_root))
        info["disk_free_gb"] = round(disk.free / (1024**3), 2)

        info["recommended"] = self._recommend(info)
        return info

    def _recommend(self, info: Dict) -> str:
        if info["disk_free_gb"] < self.model_spec["size_mb"] / 1024 + 2:
            return "⚠️ Disco insuficiente — elige un modelo más pequeño"
        if not info["cuda_available"] and self.model_spec["params"] in ("3B", "2B"):
            return "⚠️ Sin GPU — entrenamiento lento en CPU, usa LoRA + 4-bit"
        if not info["cuda_available"] and self.model_spec["params"] in ("0.5B", "1.5B"):
            return "✅ Modelo adecuado para CPU"
        if info["cuda_available"]:
            return "✅ GPU detectada — entrenamiento óptimo"
        return "Verifica recursos"

    # ------------------------------------------------------------------ #
    #  Entorno virtual
    # ------------------------------------------------------------------ #
    def create_venv(self) -> Path:
        """Crea un entorno virtual para el entrenamiento."""
        if self.venv_dir.exists():
            logger.info(f"Entorno virtual ya existe: {self.venv_dir}")
            return self.venv_dir

        logger.info(f"Creating virtual environment: {self.venv_dir}")
        subprocess.run(
            [sys.executable, "-m", "venv", str(self.venv_dir)],
            check=True,
        )
        logger.info("Virtual environment created")
        return self.venv_dir

    def get_python(self) -> str:
        """Path al ejecutable de Python del venv."""
        if os.name == "nt":
            return str(self.venv_dir / "Scripts" / "python.exe")
        return str(self.venv_dir / "bin" / "python")

    def get_pip(self) -> str:
        """Path al ejecutable de pip del venv."""
        if os.name == "nt":
            return str(self.venv_dir / "Scripts" / "pip.exe")
        return str(self.venv_dir / "bin" / "pip")

    def install_deps(self) -> None:
        """Instala dependencias en el venv."""
        pip = self.get_pip()

        logger.info("Installing PyTorch (CPU or CUDA)...")
        cuda_available = self._detect_cuda()

        if cuda_available:
            subprocess.run(
                [pip, "install", "torch", "torchvision", "torchaudio",
                 "--index-url", "https://download.pytorch.org/whl/cu121"],
                check=False,
            )
        else:
            subprocess.run([pip, "install", "torch"], check=False)

        logger.info(f"Installing {len(PC_TRAINING_DEPS)} training packages...")
        for pkg in PC_TRAINING_DEPS:
            if pkg.startswith("torch"):
                continue
            logger.info(f"  → {pkg}")
            subprocess.run([pip, "install", pkg], check=False)

        logger.info("Dependencies installed")

    def _detect_cuda(self) -> bool:
        """Detecta si hay GPU NVIDIA disponible."""
        try:
            result = subprocess.run(
                ["nvidia-smi"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    #  Descarga del modelo
    # ------------------------------------------------------------------ #
    def download_model(self) -> str:
        """
        Descarga el modelo base desde HuggingFace al directorio local.
        Returns: ruta local del modelo descargado
        """
        from huggingface_hub import snapshot_download

        target_dir = self.model_cache_dir / self.model_key
        if target_dir.exists() and any(target_dir.iterdir()):
            logger.info(f"Model already downloaded: {target_dir}")
            return str(target_dir)

        logger.info(f"Downloading model: {self.model_id} → {target_dir}")

        token = self.hf_token if self.hf_token else None
        local_path = snapshot_download(
            self.model_id,
            cache_dir=str(self.model_cache_dir),
            local_dir=str(target_dir),
            token=token,
            local_files_only=False,
        )
        logger.info(f"Model downloaded to: {local_path}")
        return local_path

    # ------------------------------------------------------------------ #
    #  Preparación de datos
    # ------------------------------------------------------------------ #
    def prepare_training_data(self) -> str:
        """
        Asegura que training-data.jsonl existe y es válido.
        Si no existe, genera datos de muestra.
        """
        data_file = self.repo_root / "training-data.jsonl"
        if data_file.exists():
            count = sum(1 for _ in open(data_file, encoding="utf-8"))
            logger.info(f"Training data found: {count} samples ({data_file})")
            return str(data_file)

        logger.info("No training-data.jsonl found. Generating sample data...")
        subprocess.run(
            [self.get_python(), str(self.repo_root / "scripts" / "collect-training-data.py")],
            check=False,
        )
        if data_file.exists():
            count = sum(1 for _ in open(data_file, encoding="utf-8"))
            logger.info(f"Generated {count} training samples")
            return str(data_file)

        logger.warning("Could not generate training data")
        return ""

    # ------------------------------------------------------------------ #
    #  Integración con finetune-model.py
    # ------------------------------------------------------------------ #
    def create_run_script(self, output_dir: str = "./fine-tuned-ame") -> str:
        """Crea un script wrapper para ejecutar el fine-tuning."""
        script_path = Path("run_training.sh" if os.name != "nt" else "run_training.bat")

        if os.name == "nt":
            content = f"""@echo off
REM AURA Fine-tuning Runner
call {self.venv_dir}\\Scripts\\activate
python scripts/finetune-model.py ^
  --model-id {self.model_id} ^
  --data training-data.jsonl ^
  --output-dir {output_dir} ^
  --epochs 3 ^
  --lr 1e-4 ^
  --batch-size 4 ^
  --max-length 2048
pause
"""
        else:
            content = f"""#!/usr/bin/env bash
# AURA Fine-tuning Runner
source {self.venv_dir}/bin/activate
python scripts/finetune-model.py \\
  --model-id {self.model_id} \\
  --data training-data.jsonl \\
  --output-dir {output_dir} \\
  --epochs 3 \\
  --lr 1e-4 \\
  --batch-size 4 \\
  --max-length 2048
"""
            script_path.chmod(0o755)

        script_path.write_text(content)
        logger.info(f"Run script created: {script_path}")
        return str(script_path)

    def create_config_file(self) -> str:
        """Crea un archivo de configuración JSON para referencia futura."""
        config = {
            "model_key": self.model_key,
            "model_id": self.model_id,
            "params": self.model_spec["params"],
            "size_mb": self.model_spec["size_mb"],
            "requires_gpu": self.model_spec["requires_gpu"],
            "venv_dir": str(self.venv_dir),
            "model_cache_dir": str(self.model_cache_dir),
            "training_script": "scripts/finetune-model.py",
            "training_data": "training-data.jsonl",
            "output_dir": "./fine-tuned-ame",
            "created_at": datetime.now().isoformat(),
        }
        config_path = self.repo_root / "training_config_pc.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Config saved: {config_path}")
        return str(config_path)

    # ------------------------------------------------------------------ #
    #  Despliegue a Termux
    # ------------------------------------------------------------------ #
    def deploy_to_termux(
        self,
        termux_host: str = "192.168.18.21",
        termux_port: int = 8022,
        termux_user: str = "u0_a252",
    ) -> bool:
        """
        Despliega el modelo y datos al Termux via SSH.
        """
        from scp import SCPClient
        import paramiko

        target = f"{termux_user}@{termux_host}"
        remote_base = "~/AME_AI/"

        logger.info(f"Deploying to Termux: {target}:{termux_port}")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(
                hostname=termux_host,
                port=termux_port,
                username=termux_user,
                key_filename=os.path.expanduser("~/.ssh/id_rsa"),
                timeout=15,
            )
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            logger.info("Usa Termux Connect para forzar restart de sshd:")
            logger.info("  PowerShell> .\\scripts\\termux-connect.ps1 -Diagnose")
            return False

        # Create remote directory
        ssh.exec_command(f"mkdir -p {remote_base}models {remote_base}data")

        # Upload model
        model_path = self.model_cache_dir / self.model_key
        if model_path.exists():
            logger.info(f"Uploading model ({self.model_spec['size_mb']}MB)...")
            scp = SCPClient(ssh.get_transport())
            scp.put(str(model_path), f"{remote_base}models/", recursive=True)
            scp.close()

        # Upload training data
        data_file = self.repo_root / "training-data.jsonl"
        if data_file.exists():
            scp = SCPClient(ssh.get_transport())
            scp.put(str(data_file), f"{remote_base}data/training-data.jsonl")
            scp.close()

        # Upload trainer module
        trainer_src = self.repo_root / "scripts" / "termux_ai_trainer.py"
        if trainer_src.exists():
            scp = SCPClient(ssh.get_transport())
            scp.put(str(trainer_src), f"{remote_base}termux_ai_trainer.py")
            scp.close()

        ssh.close()
        logger.info(f"✅ Deploy complete → {remote_base}")
        logger.info(f"   En Termux: cd ~/{remote_base} && python termux_ai_trainer.py train")
        return True

    # ------------------------------------------------------------------ #
    #  Pipeline completo
    # ------------------------------------------------------------------ #
    def run_full_setup(self, deploy: bool = False) -> Dict:
        """Ejecuta el setup completo: venv + deps + download + data + deploy."""
        results: Dict = {}

        # 1. Diagnóstico
        diag = self.diagnose_pc()
        logger.info("=== PC Resource Diagnosis ===")
        for k, v in diag.items():
            logger.info(f"  {k}: {v}")
        results["diagnosis"] = diag

        # 2. Venv
        self.create_venv()
        results["venv"] = str(self.venv_dir)

        # 3. Dependencies
        self.install_deps()
        results["deps_installed"] = True

        # 4. Download model
        model_path = self.download_model()
        results["model_path"] = model_path
        results["model_id"] = self.model_id

        # 5. Prepare training data
        data_path = self.prepare_training_data()
        results["training_data"] = data_path

        # 6. Create runner scripts
        self.create_run_script()
        self.create_config_file()
        results["config_file"] = "training_config_pc.json"

        # 7. Optional: deploy to Termux
        if deploy:
            ok = self.deploy_to_termux()
            results["deployed_to_termux"] = ok

        return results

    def list_models(self) -> None:
        """Lista todos los modelos disponibles con specs."""
        print(f"{'Key':<14} {'Hf ID':<42} {'Size':>7}  {'Params':>5}  {'GPU?'}")
        print("-" * 80)
        for key, spec in PC_MODELS.items():
            gpu = "Sí" if spec["requires_gpu"] else "No"
            print(f"{key:<14} {spec['hf_id']:<42} {spec['size_mb']:>6}MB  {spec['params']:>5}  {gpu:>3}")


# ---------------------------------------------------------------------- #
#  CLI
# ---------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(
        description="AURA PC Model Downloader & Training Environment Setup",
    )
    p.add_argument(
        "--model",
        default="qwen-1.5b",
        choices=list(PC_MODELS.keys()),
        help="Modelo ligero a descargar (default: qwen-1.5b)",
    )
    p.add_argument("--venv-dir", default="venv-training", help="Directorio del venv")
    p.add_argument("--model-dir", default="models", help="Directorio para modelos")
    p.add_argument("--hf-token", default=None, help="Token de HuggingFace")
    p.add_argument("--deploy-termux", action="store_true", help="Desplegar a Termux al finalizar")
    p.add_argument("--termux-host", default="192.168.18.21", help="IP del Termux")
    p.add_argument("--termux-port", type=int, default=8022, help="Puerto SSH de Termux")
    p.add_argument("--termux-user", default="u0_a252", help="Usuario de SSH de Termux")

    sub = p.add_subparsers(dest="command")

    s_list = sub.add_parser("list-models", help="Listar modelos disponibles")
    s_list.set_defaults(func=lambda a: PCPreSetup().list_models())

    s_diag = sub.add_parser("diagnose", help="Diagnosticar recursos del PC")
    s_diag.set_defaults(func=lambda a: print(json.dumps(PCPreSetup(a.model).diagnose_pc(), indent=2, default=str)))

    s_dl = sub.add_parser("download", help="Solo descargar el modelo")
    s_dl.set_defaults(func=lambda a: print(PCPreSetup(a.model, a.venv_dir, a.model_dir, a.hf_token).download_model()))

    s_deps = sub.add_parser("install-deps", help="Solo instalar dependencias en venv")
    s_deps.set_defaults(func=lambda a: (
        PCPreSetup(a.model, a.venv_dir, a.model_dir, a.hf_token).create_venv(),
        PCPreSetup(a.model, a.venv_dir, a.model_dir, a.hf_token).install_deps(),
    ))

    s_run = sub.add_parser("run", help="Ejecutar setup completo (default)")
    s_run.set_defaults(func=lambda a: print(json.dumps(PCPreSetup(
        a.model, a.venv_dir, a.model_dir, a.hf_token
    ).run_full_setup(deploy=a.deploy_termux), indent=2, default=str)))

    args = p.parse_args()

    if not args.command:
        args.command = "run"

    if hasattr(args, "func"):
        args.func(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
