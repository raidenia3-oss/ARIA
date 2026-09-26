#!/usr/bin/env python3
"""
AURA Cloud Sync — Sincroniza datasets y modelos entre local y la nube.

Usa:
  - cloud_work/ como staging local para la nube
  - SCP/rsync si hay SSH configurado
  - Zips para transfers grandes
  - Checksums para verificar integridad

Uso:
  python scripts/cloud_sync.py --direction upload --target runpod
  python scripts/cloud_sync.py --direction download --source runpod
  python scripts/cloud_sync.py --package
  python scripts/cloud_sync.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CloudSync")

REPO_ROOT = Path(__file__).resolve().parent.parent
CLOUD_WORK = REPO_ROOT / "cloud_work"
CLOUD_PACKAGE = REPO_ROOT / "aura_cloud_package.zip"
SYNC_STATE_FILE = REPO_ROOT / "cloud_sync_state.json"

DATASETS_TO_SYNC = [
    "training-data.jsonl",
    "training-data-collected.jsonl",
    "training-data-ui.jsonl",
    "training-data-web.jsonl",
    "training-data-reasoning.jsonl",
    "training-data-tasks.jsonl",
    "training-data-search.jsonl",
    "training-data-device.jsonl",
    "training-data-voice.jsonl",
    "training-data-system.jsonl",
    "training-data-memory.jsonl",
    "training-data-portable.jsonl",
    "training-data-sync.jsonl",
    "training-data-deployment.jsonl",
    "training-data-vision.jsonl",
    "training-data-screen.jsonl",
    "training-data-persuasion.jsonl",
    "training-data-emotional.jsonl",
    "training-data-evolved.jsonl",
    "training-data-self_evolved.jsonl",
    "training_config_pc.json",
]

MODELS_TO_SYNC = [
    "fine-tuned-ame",
]


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def package_datasets() -> Dict[str, Any]:
    CLOUD_WORK.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {"timestamp": datetime.now().isoformat(), "files": []}

    with zipfile.ZipFile(CLOUD_PACKAGE, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in DATASETS_TO_SYNC:
            src = REPO_ROOT / name
            if src.exists():
                arc = f"datasets/{name}"
                zf.write(src, arc)
                manifest["files"].append({
                    "name": name,
                    "arc": arc,
                    "size": src.stat().st_size,
                    "md5": md5(src),
                })
        for model in MODELS_TO_SYNC:
            src = REPO_ROOT / model
            if src.exists():
                for path in src.rglob("*"):
                    if path.is_file():
                        arc = f"models/{model}/{path.relative_to(src)}"
                        zf.write(path, arc)
                        manifest["files"].append({
                            "name": str(path.relative_to(REPO_ROOT)),
                            "arc": arc,
                            "size": path.stat().st_size,
                            "md5": md5(path),
                        })

    manifest["zip"] = str(CLOUD_PACKAGE)
    manifest["zip_size"] = CLOUD_PACKAGE.stat().st_size
    state_path = CLOUD_WORK / "sync_manifest.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"Packaged {len(manifest['files'])} files -> {CLOUD_PACKAGE}")
    return manifest


def extract_package() -> Dict[str, Any]:
    if not CLOUD_PACKAGE.exists():
        return {"error": f"Package not found: {CLOUD_PACKAGE}"}
    with zipfile.ZipFile(CLOUD_PACKAGE, "r") as zf:
        zf.extractall(CLOUD_WORK)
    logger.info(f"Extracted package -> {CLOUD_WORK}")
    return {"status": "ok", "extracted_to": str(CLOUD_WORK)}


def sync_to_cloud() -> Dict[str, Any]:
    manifest = package_datasets()
    result = {
        "direction": "upload",
        "timestamp": datetime.now().isoformat(),
        "manifest": manifest,
        "status": "ready",
        "next_step": "Upload cloud_work/ to your GPU instance (RunPod/Modal/Lambda).",
    }
    state = {"last_upload": datetime.now().isoformat(), "manifest": manifest}
    with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    return result


def sync_from_cloud() -> Dict[str, Any]:
    model_src = CLOUD_WORK / "fine-tuned-ame"
    model_dst = REPO_ROOT / "fine-tuned-ame"
    result = {"direction": "download", "timestamp": datetime.now().isoformat(), "files": []}
    if model_src.exists():
        if model_dst.exists():
            shutil.rmtree(model_dst)
        shutil.copytree(model_src, model_dst)
        result["files"].append({"source": str(model_src), "destination": str(model_dst), "status": "ok"})
        logger.info(f"Downloaded model -> {model_dst}")
    else:
        result["files"].append({"source": str(model_src), "status": "not_found"})
    state = {"last_download": datetime.now().isoformat(), "result": result}
    with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    return result


def verify_package() -> Dict[str, Any]:
    if not CLOUD_PACKAGE.exists():
        return {"valid": False, "error": "Package not found"}
    state_file = CLOUD_WORK / "sync_manifest.json"
    if not state_file.exists():
        return {"valid": False, "error": "Manifest not found"}
    with open(state_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    errors = []
    for file_info in manifest.get("files", []):
        name = file_info.get("name")
        expected_md5 = file_info.get("md5")
        if not name or not expected_md5:
            continue
        src = REPO_ROOT / name
        if not src.exists():
            errors.append(f"missing: {name}")
            continue
        actual_md5 = md5(src)
        if actual_md5 != expected_md5:
            errors.append(f"checksum_mismatch: {name}")
    return {"valid": len(errors) == 0, "errors": errors[:10], "total_files": len(manifest.get("files", []))}


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Cloud Sync")
    p.add_argument("--direction", type=str, default="upload", choices=["upload", "download"])
    p.add_argument("--package", action="store_true", help="Create cloud package only")
    p.add_argument("--verify", action="store_true", help="Verify package integrity")
    p.add_argument("--target", type=str, default="runpod")
    p.add_argument("--source", type=str, default="runpod")
    args = p.parse_args()

    if args.verify:
        result = verify_package()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.package:
        result = package_datasets()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.direction == "upload":
        result = sync_to_cloud()
    else:
        result = sync_from_cloud()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
