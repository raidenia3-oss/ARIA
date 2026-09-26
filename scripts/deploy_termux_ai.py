#!/usr/bin/env python3
"""
AURA Termux AI Deploy — Despliega el módulo de entrenamiento y datos al celular.

Usa la infraestructura SSH existente (scripts/termux-connect.ps1) para:
  1. Verificar conectividad SSH a Termux
  2. Instalar dependencias Python en Termux (torch, transformers, peft, etc.)
  3. Subir el modelo descargado desde PC
  4. Subir los datos de entrenamiento
  5. Subir el módulo termux_ai_trainer.py
  6. Ejecutar entrenamiento on-device desde PC

Configuración SSH (ver scripts/termux-connect.ps1):
  Host:  192.168.18.21
  Port:  8022
  User:  u0_a252
  Key:   ~/.ssh/id_rsa

Uso:
  python scripts/deploy_termux_ai.py --diagnose     # chequear conexion
  python scripts/deploy_termux_ai.py --deploy       # full deploy
  python scripts/deploy_termux_ai.py --train        # deploy + entrenar
  python scripts/deploy_termux_ai.py --sync-model   # solo subir modelo
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("TermuxDeploy")

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTE_BASE = "~/AME_AI"
REMOTE_DIRS = [f"{REMOTE_BASE}", f"{REMOTE_BASE}/models", f"{REMOTE_BASE}/data"]


class TermuxDeployer:
    """Despliega módulos de IA a Termux y opcionalmente entrena allí."""

    def __init__(
        self,
        host: str = "192.168.18.21",
        port: int = 8022,
        user: str = "u0_a252",
        key_path: str = "~/.ssh/id_rsa",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = os.path.expanduser(key_path)
        self.target = f"{user}@{host}"
        self.scp_prefix = f"-P {port} -i {self.key_path} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"

    # ------------------------------------------------------------------ #
    #  Conectividad
    # ------------------------------------------------------------------ #
    def check_ssh(self) -> bool:
        """Verifica que sshd está corriendo en Termux y la key funciona."""
        logger.info(f"Testing SSH to {self.target}:{self.port}...")
        result = subprocess.run(
            ["ssh", *self.scp_prefix.split(), self.target, "echo CONNECTED"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0 and "CONNECTED" in result.stdout:
            logger.info("✅ SSH conectado")
            return True
        logger.error(f"❌ SSH falló (exit {result.returncode}): {result.stderr.strip()}")
        logger.info("💡 Ejecuta: .\\scripts\\termux-connect.ps1 -Diagnose")
        logger.info("   O fuerza restart: pkill sshd; sshd -p 8022 -o ListenAddress=0.0.0.0")
        return False

    def ssh(self, command: str, silent: bool = False) -> subprocess.CompletedProcess:
        """Ejecuta un comando remoto en Termux."""
        if not silent:
            logger.info(f"[SSH] {command}")
        result = subprocess.run(
            ["ssh", *self.scp_prefix.split(), self.target, command],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            if result.stdout.strip():
                print(result.stdout)
            return result
        logger.error(f"SSH error: {result.stderr.strip()}")
        return result

    def scp_upload(self, local_path: str, remote_path: str) -> bool:
        """Sube un archivo/directorio a Termux via SCP."""
        logger.info(f"[SCP] {local_path} → {self.target}:{remote_path}")
        cmd = ["scp", *self.scp_prefix.split(), "-r", local_path, f"{self.target}:{remote_path}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            logger.info("✅ Upload exitoso")
            return True
        logger.error(f"❌ SCP falló: {result.stderr.strip()}")
        return False

    # ------------------------------------------------------------------ #
    #  Termux environment
    # ------------------------------------------------------------------ #
    def setup_termux_python(self) -> bool:
        """Instala Python 3 + pip + dependencias de ML en Termux."""
        logger.info("Setting up Termux Python environment...")

        commands = [
            "pkg update -y",
            "pkg install -y python git",
            f"{sys.executable} -m pip install --upgrade pip",
            "pip install torch transformers peft datasets accelerate "
            "bitsandbytes huggingface-hub psutil paramiko scp",
        ]

        for cmd in commands:
            result = self.ssh(cmd, silent=True)
            if result.returncode != 0 and "already" not in (result.stderr + result.stdout).lower():
                logger.warning(f"  ⚠️ {cmd} → exit {result.returncode}")

        logger.info("✅ Termux Python environment ready")
        return True

    def create_remote_dirs(self) -> bool:
        """Crea directorios en Termux."""
        for d in REMOTE_DIRS:
            result = self.ssh(f"mkdir -p {d}", silent=True)
            if result.returncode != 0:
                logger.warning(f"  Could not create {d}")
        return True

    # ------------------------------------------------------------------ #
    #  Subida de artefactos
    # ------------------------------------------------------------------ #
    def upload_trainer(self) -> bool:
        """Sube termux_ai_trainer.py al celular."""
        local = REPO_ROOT / "scripts" / "termux_ai_trainer.py"
        if not local.exists():
            logger.error(f"Trainer not found: {local}")
            return False
        return self.scp_upload(str(local), f"{REMOTE_BASE}/termux_ai_trainer.py")

    def upload_training_data(self) -> bool:
        """Sube training-data.jsonl al celular."""
        local = REPO_ROOT / "training-data.jsonl"
        if not local.exists():
            logger.warning("No training-data.jsonl found — generando datos de muestra...")
            subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "collect-training-data.py")],
                cwd=str(REPO_ROOT),
            )
        if not local.exists():
            logger.error("Still no training data after generation attempt")
            return False
        return self.scp_upload(str(local), f"{REMOTE_BASE}/data/training-data.jsonl")

    def upload_model(self, model_key: str = "qwen-0.5b", model_dir: str = "models") -> bool:
        """Sube el modelo descargado por PC al celular."""
        model_path = REPO_ROOT / model_dir / model_key
        if not model_path.exists():
            logger.error(f"Model not found: {model_path}")
            logger.info("Run: python scripts/setup_pc_training.py --model {model_key}")
            return False

        size_mb = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file()) / (1024**2)
        logger.info(f"Uploading model ({size_mb:.0f} MB)...")
        return self.scp_upload(str(model_path), f"{REMOTE_BASE}/models/{model_key}")

    def upload_config(self, model_key: str = "qwen-0.5b") -> bool:
        """Crea y sube un config.json con la configuración."""
        config = {
            "model_key": model_key,
            "model_name": f"models/{model_key}",
            "training_data": "data/training-data.jsonl",
            "output_dir": "trained-output",
            "epochs": 1,
            "lr": 5e-5,
            "max_length": 512,
            "use_lora": True,
        }
        config_path = Path("/tmp/ame_termux_config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        return self.scp_upload(str(config_path), f"{REMOTE_BASE}/config.json")

    # ------------------------------------------------------------------ #
    #  Entrenamiento on-device
    # ------------------------------------------------------------------ #
    def train_on_termux(
        self,
        model_key: str = "qwen-0.5b",
        epochs: int = 1,
        lr: float = 5e-5,
    ) -> Optional[str]:
        """Ejecuta el entrenamiento en el celular via SSH."""
        remote_script = (
            f"cd {REMOTE_BASE} && "
            f"PYTHONPATH={REMOTE_BASE} "
            f"python termux_ai_trainer.py train "
            f"--model {model_key} "
            f"--data {REMOTE_BASE}/data/training-data.jsonl "
            f"--output {REMOTE_BASE}/trained-output "
            f"--epochs {epochs} "
            f"--lr {lr} "
            f"--max-length 512"
        )

        logger.info("Iniciando entrenamiento on-device en Termux...")
        result = self.ssh(remote_script, silent=False)
        if result.returncode == 0:
            logger.info("✅ Entrenamiento completado en Termux")
            return result.stdout
        logger.error(f"❌ Entrenamiento falló (exit {result.returncode})")
        return result.stderr if result.stderr else None

    def download_trained_model(self, remote_model_dir: str = "trained-output") -> bool:
        """Descarga el modelo entrenado desde el celular a PC."""
        remote_path = f"{REMOTE_BASE}/{remote_model_dir}"
        local_dir = REPO_ROOT / "termux-trained-output"
        local_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading trained model: {self.target}:{remote_path} → {local_dir}")
        cmd = [
            "scp", *self.scp_prefix.split(), "-r",
            f"{self.target}:{remote_path}",
            str(local_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            logger.info(f"✅ Modelo descargado a: {local_dir}")
            return True
        logger.error(f"❌ SCP download falló: {result.stderr.strip()}")
        return False

    # ------------------------------------------------------------------ #
    #  Pipeline completo
    # ------------------------------------------------------------------ #
    def diagnose(self) -> Dict:
        """Diagnóstico completo de conectividad."""
        results: Dict = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "key_exists": os.path.exists(self.key_path),
            "ssh_connected": False,
        }

        if not results["key_exists"]:
            logger.error(f"SSH key not found: {self.key_path}")
            logger.info("Run: .\\scripts\\copy-ssh-key-to-termux.ps1")
            return results

        results["ssh_connected"] = self.check_ssh()

        if results["ssh_connected"]:
            # Get system info from Termux
            info = self.ssh("python -c \"import platform; print(platform.platform())\"", silent=True)
            results["termux_platform"] = info.stdout.strip() if info.returncode == 0 else "unknown"

            deps = self.ssh("python -c \"import torch; print(torch.__version__)\"", silent=True)
            results["torch_installed"] = deps.returncode == 0

            if not results["torch_installed"]:
                results["recommendation"] = "Run --setup-python to install ML deps"
            else:
                results["recommendation"] = "Listo para entrenar — usa --train"

        return results

    def full_deploy(
        self,
        model_key: str = "qwen-0.5b",
        model_dir: str = "models",
        setup_python: bool = True,
    ) -> bool:
        """Despliegue completo: dirs + python + model + data + trainer + config."""
        if not self.check_ssh():
            logger.error("SSH no conecta. Abortando.")
            return False

        logger.info("=== Full Deploy to Termux ===")

        self.create_remote_dirs()

        if setup_python:
            self.setup_termux_python()

        ok = True
        ok &= self.upload_trainer()
        ok &= self.upload_training_data()
        ok &= self.upload_model(model_key, model_dir)
        ok &= self.upload_config(model_key)

        return ok


# ---------------------------------------------------------------------- #
#  CLI
# ---------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(
        description="AURA Termux AI Deploy — deploy + train on-device",
    )
    p.add_argument("--host", default="192.168.18.21", help="IP del Termux")
    p.add_argument("--port", type=int, default=8022, help="Puerto SSH")
    p.add_argument("--user", default="u0_a252", help="Usuario SSH")
    p.add_argument("--key", default="~/.ssh/id_rsa", help="Clave SSH privada")
    p.add_argument("--model", default="qwen-0.5b", help="Modelo a usar en Termux")
    p.add_argument("--model-dir", default="models", help="Dir de modelos en PC")

    sub = p.add_subparsers(dest="command")

    s_diag = sub.add_parser("diagnose", help="Diagnóstico de conectividad SSH")
    s_diag.set_defaults(func=lambda a: print(json.dumps(
        TermuxDeployer(a.host, a.port, a.user, a.key).diagnose(), indent=2, default=str
    )))

    s_setup = sub.add_parser("setup-python", help="Instalar Python + deps de ML en Termux")
    s_setup.set_defaults(func=lambda a: TermuxDeployer(a.host, a.port, a.user, a.key).setup_termux_python())

    s_deploy = sub.add_parser("deploy", help="Deploy completo al celular")
    s_deploy.add_argument("--no-python-setup", action="store_true")
    s_deploy.set_defaults(func=lambda a: TermuxDeployer(
        a.host, a.port, a.user, a.key
    ).full_deploy(
        model_key=a.model, model_dir=a.model_dir,
        setup_python=not a.no_python_setup,
    ))

    s_train = sub.add_parser("train", help="Deploy + entrenar en el celular")
    s_train.add_argument("--epochs", type=int, default=1)
    s_train.add_argument("--lr", type=float, default=5e-5)
    s_train.add_argument("--download-result", action="store_true", help="Descargar modelo entrenado después")
    s_train.set_defaults(func=lambda a: (
        TermuxDeployer(a.host, a.port, a.user, a.key).full_deploy(a.model, a.model_dir),
        TermuxDeployer(a.host, a.port, a.user, a.key).train_on_termux(a.model, a.epochs, a.lr),
        TermuxDeployer(a.host, a.port, a.user, a.key).download_trained_model() if a.download_result else None,
    ))

    s_dl = sub.add_parser("download-model", help="Subir modelo al celular")
    s_dl.set_defaults(func=lambda a: TermuxDeployer(a.host, a.port, a.user, a.key).upload_model(a.model, a.model_dir))

    args = p.parse_args()

    # Default to diagnose if no command
    if not args.command:
        args.command = "diagnose"

    if hasattr(args, "func"):
        args.func(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
