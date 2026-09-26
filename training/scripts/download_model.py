"""Descarga el modelo base Qwen2.5-0.5B-Instruct a models/qwen-0.5b/."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env.ai")

token = os.getenv("HF_TOKEN")
if not token:
    print("ERROR: HF_TOKEN no configurado")
    sys.exit(1)

from huggingface_hub import snapshot_download

target = Path(__file__).resolve().parents[2] / "models" / "qwen-0.5b"
target.mkdir(parents=True, exist_ok=True)

print(f"Descargando Qwen/Qwen2.5-0.5B-Instruct -> {target}")
snapshot_download(
    repo_id="Qwen/Qwen2.5-0.5B-Instruct",
    local_dir=str(target),
    token=token,
)

# Verificar tamaño
total = 0
count = 0
for dirpath, _, filenames in os.walk(target):
    for f in filenames:
        fp = os.path.join(dirpath, f)
        total += os.path.getsize(fp)
        count += 1

print(f"OK: {count} archivos, {total / 1e9:.2f} GB")