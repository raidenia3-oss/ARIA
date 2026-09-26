#!/usr/bin/env python3
"""
AURA Sync Engine — Motor de sincronización de conocimiento entre instancias de AURA.

Sincroniza datasets, memoria, configuraciones y modelos entre:
  - PC principal (Windows/Linux)
  - Instancias Termux
  - Servidores remotos
  - Entornos portables (USB)
  - Otros dispositivos vinculados

Características:
  - Sincronización incremental por checksum
  - Resolución de conflictos por timestamp
  - Compresión de datasets grandes
  - Vinculación por código AURA-XXXX
  - Modo offline con cola de cambios

Uso:
  python scripts/sync_engine.py --push --to TERMINAL-ID
  python scripts/sync_engine.py --pull --from TERMINAL-ID
  python scripts/sync_engine.py --link --pair-with TERMINAL-ID
  python scripts/sync_engine.py --status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SyncEngine")

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNC_DIR = REPO_ROOT / "sync"
INSTANCE_ID_FILE = REPO_ROOT / ".aura_instance_id"
SYNC_MANIFEST = SYNC_DIR / "manifest.json"


class InstanceRegistry:
    """Registro local de instancias vinculadas."""

    def __init__(self):
        self.instances: Dict[str, Dict] = {}
        self._load()

    def _load(self) -> None:
        if SYNC_MANIFEST.exists():
            try:
                data = json.loads(SYNC_MANIFEST.read_text(encoding="utf-8"))
                self.instances = data.get("instances", {})
            except Exception:
                self.instances = {}

    def save(self) -> None:
        SYNC_DIR.mkdir(parents=True, exist_ok=True)
        manifest = {
            "local_instance": self.get_local_id(),
            "instances": self.instances,
            "updated_at": __import__("datetime").datetime.now().isoformat(),
        }
        SYNC_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_local_id(self) -> str:
        if INSTANCE_ID_FILE.exists():
            return INSTANCE_ID_FILE.read_text(encoding="utf-8").strip()
        instance_id = "aura-" + hashlib.md5(str(REPO_ROOT).encode()).hexdigest()[:8]
        INSTANCE_ID_FILE.write_text(instance_id, encoding="utf-8")
        return instance_id

    def register(self, instance_id: str, metadata: Dict) -> None:
        self.instances[instance_id] = {
            "metadata": metadata,
            "last_seen": __import__("datetime").datetime.now().isoformat(),
            "status": "active",
        }
        self.save()

    def unregister(self, instance_id: str) -> None:
        if instance_id in self.instances:
            del self.instances[instance_id]
            self.save()


class FileChecksum:
    """Calcula checksums para detectar cambios."""

    @staticmethod
    def md5(path: Path) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def size(path: Path) -> int:
        return path.stat().st_size if path.exists() else 0


class DatasetPackager:
    """Empaqueta datasets para sincronización."""

    def __init__(self, source_dir: Path, output_dir: Path):
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def package(self, dataset_names: List[str]) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        zip_path = self.output_dir / f"datasets_{ts}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in dataset_names:
                p = self.source_dir / name
                if p.exists():
                    zf.write(p, p.name)
                    logger.info(f"Packaged: {name}")
        return zip_path

    def extract(self, zip_path: Path) -> List[str]:
        extracted = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                zf.extract(member, self.source_dir)
                extracted.append(member)
        return extracted


class SyncEngine:
    """Motor principal de sincronización."""

    def __init__(self):
        self.registry = InstanceRegistry()
        self.local_id = self.registry.get_local_id()

    def link(self, other_instance_id: str) -> Dict:
        metadata = {
            "platform": platform.system(),
            "hostname": platform.node(),
            "python": sys.version,
            "linked_at": __import__("datetime").datetime.now().isoformat(),
        }
        self.registry.register(other_instance_id, metadata)
        logger.info(f"Linked with: {other_instance_id}")
        return {"status": "linked", "instance_id": other_instance_id, "metadata": metadata}

    def unlink(self, instance_id: str) -> Dict:
        self.registry.unregister(instance_id)
        logger.info(f"Unlinked: {instance_id}")
        return {"status": "unlinked", "instance_id": instance_id}

    def push(self, target_instance_id: str, datasets: Optional[List[str]] = None) -> Dict:
        if datasets is None:
            datasets = [
                "training-data.jsonl",
                "training-data-reasoning.jsonl",
                "training-data-tasks.jsonl",
                "training-data-search.jsonl",
                "training-data-device.jsonl",
                "training-data-ui.jsonl",
                "training-data-web.jsonl",
                "training-config.json",
            ]

        packager = DatasetPackager(REPO_ROOT, SYNC_DIR)
        zip_path = packager.package(datasets)

        checksums = {}
        for name in datasets:
            p = REPO_ROOT / name
            if p.exists():
                checksums[name] = {"md5": FileChecksum.md5(p), "size": FileChecksum.size(p)}

        manifest = {
            "from_instance": self.local_id,
            "to_instance": target_instance_id,
            "datasets": datasets,
            "checksums": checksums,
            "zip": str(zip_path),
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        manifest_path = SYNC_DIR / f"push_{self.local_id}_to_{target_instance_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Push prepared: {zip_path}")
        return {"status": "pushed", "zip": str(zip_path), "manifest": str(manifest_path)}

    def pull(self, source_instance_id: str, zip_path: Optional[Path] = None) -> Dict:
        if zip_path is None:
            candidates = sorted(SYNC_DIR.glob(f"push_*_to_{self.local_id}_*.json"), reverse=True)
            if not candidates:
                return {"status": "error", "message": "No push manifest found"}
            manifest_path = candidates[0]
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            zip_path = Path(manifest["zip"])

        if not zip_path.exists():
            return {"status": "error", "message": f"Zip not found: {zip_path}"}

        packager = DatasetPackager(REPO_ROOT, SYNC_DIR)
        extracted = packager.extract(zip_path)

        result = {"status": "pulled", "extracted": extracted, "source": source_instance_id}
        logger.info(f"Pull complete: {len(extracted)} files")
        return result

    def status(self) -> Dict:
        linked = list(self.registry.instances.keys())
        pending_pulls = len(list(SYNC_DIR.glob(f"push_*_to_{self.local_id}_*.json")))
        pending_pushes = len(list(SYNC_DIR.glob(f"push_{self.local_id}_to_*.json")))

        return {
            "local_instance": self.local_id,
            "linked_instances": linked,
            "pending_pulls": pending_pulls,
            "pending_pushes": pending_pushes,
            "sync_dir": str(SYNC_DIR),
        }


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Sync Engine")
    p.add_argument("--link", action="store_true", help="Vincular con otra instancia")
    p.add_argument("--unlink", type=str, default=None, help="Desvincular instancia")
    p.add_argument("--push", action="store_true", help="Enviar datasets a instancia vinculada")
    p.add_argument("--pull", action="store_true", help="Recibir datasets de instancia vinculada")
    p.add_argument("--with", dest="pair_with", type=str, default=None, help="ID de instancia para vincular/push/pull")
    p.add_argument("--datasets", nargs="+", default=None, help="Lista de datasets a sincronizar")
    p.add_argument("--status", action="store_true", help="Mostrar estado de sincronización")
    args = p.parse_args()

    engine = SyncEngine()

    if args.status:
        print(json.dumps(engine.status(), indent=2, ensure_ascii=False))
        return

    if args.link and args.pair_with:
        result = engine.link(args.pair_with)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.unlink:
        result = engine.unlink(args.unlink)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.push and args.pair_with:
        result = engine.push(args.pair_with, args.datasets)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.pull and args.pair_with:
        result = engine.pull(args.pair_with)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    p.print_help()


if __name__ == "__main__":
    main()
