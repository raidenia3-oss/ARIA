#!/usr/bin/env python3
"""
AURA Self-Deployment Engine — Motor de auto-despliegue de AURA en otros dispositivos.

Permite que AURA se instale, configure y ejecute automáticamente en:
  - Windows (local, remoto via SSH)
  - Linux/WSL
  - Android/Termux
  - Raspberry Pi / ARM
  - Servidores remotos (VPS, Railway, Render)

Genera:
  - Scripts de instalación por plataforma
  - Entornos virtuales portables
  - Servicios/systemd para arranque automático
  - Códigos de vinculación entre instancias
  - Reportes de estado para la instancia principal

Uso:
  python scripts/self_deployment_engine.py --target windows --install
  python scripts/self_deployment_engine.py --target termux --install --model qwen-0.5b
  python scripts/self_deployment_engine.py --target linux --service --name aura
  python scripts/self_deployment_engine.py --generate-portable --output AURA_Portable.zip
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import random
import shutil
import string
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SelfDeployment")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"
PORTABLE_DIR = REPO_ROOT / "AURA_Portable"

SUPPORTED_TARGETS = ["windows", "linux", "termux", "macos", "raspberry-pi", "docker"]

MODELS_BY_PLATFORM: Dict[str, Dict[str, Dict]] = {
    "windows": {
        "qwen-1.5b": {"hf_id": "Qwen/Qwen2.5-1.5B", "size_mb": 2955, "requires_gpu": False},
        "qwen-0.5b": {"hf_id": "Qwen/Qwen2.5-0.5B", "size_mb": 500, "requires_gpu": False},
        "phi3-mini": {"hf_id": "microsoft/Phi-3-mini-4k-instruct", "size_mb": 2000, "requires_gpu": False},
    },
    "linux": {
        "qwen-1.5b": {"hf_id": "Qwen/Qwen2.5-1.5B", "size_mb": 2955, "requires_gpu": False},
        "qwen-0.5b": {"hf_id": "Qwen/Qwen2.5-0.5B", "size_mb": 500, "requires_gpu": False},
        "tinyllama": {"hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "size_mb": 2000, "requires_gpu": False},
    },
    "termux": {
        "qwen-0.5b": {"hf_id": "Qwen/Qwen2.5-0.5B", "size_mb": 500, "requires_gpu": False},
        "tinyllama": {"hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "size_mb": 2000, "requires_gpu": False},
        "gemma-2b": {"hf_id": "google/gemma-2b-it", "size_mb": 5000, "requires_gpu": False},
    },
    "raspberry-pi": {
        "qwen-0.5b": {"hf_id": "Qwen/Qwen2.5-0.5B", "size_mb": 500, "requires_gpu": False},
        "tinyllama": {"hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "size_mb": 2000, "requires_gpu": False},
    },
}

PYTHON_DEPS = [
    "torch>=2.1.0",
    "transformers>=4.40.0",
    "peft>=0.10.0",
    "datasets>=2.19.0",
    "accelerate>=0.30.0",
    "bitsandbytes>=0.43.0",
    "huggingface-hub>=0.23.0",
    "scikit-learn>=1.4.0",
    "numpy>=1.26.0",
    "psutil>=5.9.0",
]


class DeploymentTarget:
    """Detecta y representa el dispositivo objetivo."""

    def __init__(self, target: Optional[str] = None):
        self.target = target or self._detect()
        self.platform = platform.system().lower()
        self.machine = platform.machine().lower()
        self.is_arm = "arm" in self.machine or "aarch64" in self.machine
        self.is_android = "android" in os.environ.get("PREFIX", "").lower() or "termux" in os.environ.get("PREFIX", "").lower()
        self.ram_gb = self._get_ram()
        self.disk_free_gb = self._get_disk_free()

    def _detect(self) -> str:
        if self.is_android or "termux" in os.environ.get("PREFIX", "").lower():
            return "termux"
        if self.is_arm:
            return "raspberry-pi"
        p = platform.system().lower()
        if p == "windows":
            return "windows"
        if p == "linux":
            return "linux"
        if p == "darwin":
            return "macos"
        return "linux"

    def _get_ram(self) -> float:
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024**3), 2)
        except Exception:
            return 0.0

    def _get_disk_free(self) -> float:
        try:
            return round(shutil.disk_usage(str(REPO_ROOT)).free / (1024**3), 2)
        except Exception:
            return 0.0

    def recommended_model(self) -> str:
        models = MODELS_BY_PLATFORM.get(self.target, MODELS_BY_PLATFORM["linux"])
        if self.ram_gb < 4 or self.disk_free_gb < 3:
            return "qwen-0.5b"
        if self.ram_gb < 8:
            return "qwen-1.5b" if self.target != "termux" else "tinyllama"
        return "qwen-1.5b"

    def to_dict(self) -> Dict:
        return {
            "target": self.target,
            "platform": self.platform,
            "machine": self.machine,
            "is_arm": self.is_arm,
            "is_android": self.is_android,
            "ram_gb": self.ram_gb,
            "disk_free_gb": self.disk_free_gb,
            "recommended_model": self.recommended_model(),
        }


class InstallerGenerator:
    """Genera scripts de instalación por plataforma."""

    def __init__(self, target: DeploymentTarget, model_key: str = "qwen-1.5b"):
        self.target = target
        self.model_key = model_key
        self.model_spec = MODELS_BY_PLATFORM.get(target.target, MODELS_BY_PLATFORM["linux"]).get(
            model_key, MODELS_BY_PLATFORM["linux"]["qwen-1.5b"]
        )

    def generate_windows(self) -> str:
        return f"""@echo off
chcp 65001 >nul
echo ==========================================
echo   AURA Self-Deployment - Windows
echo ==========================================
echo.

REM Crear directorios
if not exist venv-training mkdir venv-training
if not exist models mkdir models
if not exist fine-tuned-ame mkdir fine-tuned-ame
if not exist training-data mkdir training-data

REM Crear entorno virtual
python -m venv venv-training
call venv-training\\Scripts\\activate.bat

REM Instalar dependencias
pip install --upgrade pip
pip install {' '.join(PYTHON_DEPS)}

REM Descargar modelo
echo Descargando modelo {self.model_spec['hf_id']}...
python -c "from huggingface_hub import snapshot_download; snapshot_download('{self.model_spec['hf_id']}', local_dir='models/{self.model_key}')"

REM Configurar servicios
echo Configurando servicios...
powershell -Command "New-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run' -Name 'AURA' -Value '%~dp0venv-training\\Scripts\\python.exe %~dp0scripts\\aura_autonomous_trainer.py --auto' -PropertyType String"

echo.
echo [OK] AURA desplegada en Windows.
echo Modelo: {self.model_spec['hf_id']}
echo Ejecuta: venv-training\\Scripts\\activate.bat && python scripts\\aura_autonomous_trainer.py --auto
pause
"""

    def generate_linux(self) -> str:
        return f"""#!/bin/bash
set -e
echo "=========================================="
echo "   AURA Self-Deployment - Linux"
echo "=========================================="
echo ""

mkdir -p venv-training models fine-tuned-ame training-data

python3 -m venv venv-training
source venv-training/bin/activate

pip install --upgrade pip
pip install {' '.join(PYTHON_DEPS)}

echo "Descargando modelo {self.model_spec['hf_id']}..."
python -c "from huggingface_hub import snapshot_download; snapshot_download('{self.model_spec['hf_id']}', local_dir='models/{self.model_key}')"

echo "Configurando servicio systemd..."
sudo tee /etc/systemd/system/aura.service > /dev/null << 'EOF'
[Unit]
Description=AURA Autonomous Trainer
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory={REPO_ROOT}
ExecStart={REPO_ROOT}/venv-training/bin/python {REPO_ROOT}/scripts/aura_autonomous_trainer.py --auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable aura
sudo systemctl start aura

echo ""
echo "[OK] AURA desplegada en Linux."
echo "Modelo: {self.model_spec['hf_id']}"
echo "Servicio: sudo systemctl status aura"
"""

    def generate_termux(self) -> str:
        return f"""#!/bin/bash
echo "=========================================="
echo "   AURA Self-Deployment - Termux"
echo "=========================================="
echo ""

pkg update -y && pkg upgrade -y
pkg install python python-dev libjpeg-turbo libpng freetype openssl git -y
pip install --upgrade pip
pip install {' '.join(PYTHON_DEPS)}

mkdir -p ~/.local/share/ame/models ~/.local/share/ame/training ~/.local/share/ame/output

echo "Descargando modelo {self.model_spec['hf_id']}..."
python -c "from huggingface_hub import snapshot_download; snapshot_download('{self.model_spec['hf_id']}', local_dir='~/.local/share/ame/models/{self.model_key}')"

echo "Configurando arranque automático..."
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/aura_start.sh << 'BOOT'
#!/bin/bash
termux-wake-lock
cd ~/.local/share/ame
source venv/bin/activate
python termux_ai_trainer.py --auto
BOOT
chmod +x ~/.termux/boot/aura_start.sh

echo ""
echo "[OK] AURA desplegada en Termux."
echo "Modelo: {self.model_spec['hf_id']}"
echo "Arranque automático: ~/.termux/boot/aura_start.sh"
"""

    def generate_raspberry_pi(self) -> str:
        return self.generate_linux()  # Similar a Linux pero con optimizaciones ARM

    def generate_script(self) -> str:
        generators = {
            "windows": self.generate_windows,
            "linux": self.generate_linux,
            "termux": self.generate_termux,
            "raspberry-pi": self.generate_raspberry_pi,
            "macos": self.generate_linux,
        }
        generator = generators.get(self.target.target, self.generate_linux)
        return generator()

    def save_script(self, output_path: Path) -> None:
        script = self.generate_script()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script, encoding="utf-8")
        if self.target.target in ["linux", "termux", "raspberry-pi"]:
            output_path.chmod(0o755)
        logger.info(f"Installer script saved: {output_path}")


class PortableAuraBuilder:
    """Construye un AURA portable en un directorio/zip."""

    def __init__(self, target: DeploymentTarget, model_key: str = "qwen-0.5b"):
        self.target = target
        self.model_key = model_key
        self.build_dir = PORTABLE_DIR

    def build(self) -> Path:
        logger.info(f"Building portable AURA at {self.build_dir}")
        self.build_dir.mkdir(parents=True, exist_ok=True)

        essential_scripts = [
            "scripts/aura_autonomous_trainer.py",
            "scripts/finetune-model.py",
            "scripts/setup_pc_training.py",
            "scripts/termux_ai_trainer.py",
            "scripts/reasoning_trainer.py",
            "scripts/task_simulation_engine.py",
            "scripts/advanced_search_engine.py",
            "scripts/device_app_connector.py",
            "scripts/self_deployment_engine.py",
            "scripts/sync_engine.py",
            "scripts/voice_trainer.py",
            "scripts/memory_manager.py",
            "scripts/system_controller_trainer.py",
            "scripts/portable_aura.py",
            "training_config_pc.json",
            "requirements.txt",
        ]

        for rel_path in essential_scripts:
            src = REPO_ROOT / rel_path
            dst = self.build_dir / rel_path
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        portable_launcher = """#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scripts.portable_aura import main
main()
"""
        (self.build_dir / "aura_portable_launcher.py").write_text(portable_launcher, encoding="utf-8")

        readme = f"""# AURA Portable
Modelo: {self.model_key}
Plataforma: {self.target.target}
RAM: {self.target.ram_gb} GB
Disco libre: {self.target.disk_free_gb} GB

Uso:
  python aura_portable_launcher.py --auto
  python aura_portable_launcher.py --train
  python aura_portable_launcher.py --sync
"""
        (self.build_dir / "README_PORTABLE.md").write_text(readme, encoding="utf-8")

        logger.info(f"Portable AURA built at {self.build_dir}")
        return self.build_dir

    def package_zip(self, output_path: Path) -> None:
        self.build()
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in self.build_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(self.build_dir))
        logger.info(f"Portable package created: {output_path}")


class LinkCodeGenerator:
    """Genera códigos de vinculación entre instancias de AURA."""

    @staticmethod
    def generate(code_length: int = 8) -> str:
        return "AURA-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=code_length))

    @staticmethod
    def generate_pair() -> Tuple[str, str]:
        code_a = LinkCodeGenerator.generate()
        code_b = LinkCodeGenerator.generate()
        return code_a, code_b

    @staticmethod
    def generate_qr_data(code: str, instance_id: str) -> str:
        return json.dumps({"aura_link": code, "instance": instance_id, "protocol": "aura-sync/v1"})


def deploy(args: argparse.Namespace) -> None:
    target = DeploymentTarget(args.target)
    logger.info(f"Target detected: {target.to_dict()}")

    if args.generate_portable:
        builder = PortableAuraBuilder(target, args.model)
        if args.zip:
            builder.package_zip(Path(args.output))
        else:
            builder.build()
        return

    installer = InstallerGenerator(target, args.model)
    output_file = DEPLOY_DIR / f"install_{target.target}.{'bat' if target.target == 'windows' else 'sh'}"
    installer.save_script(output_file)

    if args.run:
        logger.info(f"Running installer for {target.target}...")
        if target.target == "windows":
            os.startfile(str(output_file))
        else:
            os.system(f"bash {output_file}")


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Self-Deployment Engine")
    p.add_argument("--target", type=str, default=None, choices=SUPPORTED_TARGETS, help="Plataforma objetivo")
    p.add_argument("--model", type=str, default=None, help="Modelo a descargar")
    p.add_argument("--install", action="store_true", help="Generar script de instalación")
    p.add_argument("--run", action="store_true", help="Ejecutar instalación automáticamente")
    p.add_argument("--generate-portable", action="store_true", help="Construir AURA portable")
    p.add_argument("--zip", action="store_true", help="Empaquetar portable en ZIP")
    p.add_argument("--output", type=str, default=str(DEPLOY_DIR / "AURA_Portable.zip"), help="Ruta de salida")
    args = p.parse_args()

    if not args.target and not args.generate_portable:
        target = DeploymentTarget()
        print(json.dumps(target.to_dict(), indent=2, ensure_ascii=False))
        return

    deploy(args)


if __name__ == "__main__":
    main()
