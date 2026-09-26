# -*- coding: utf-8 -*-
"""AURA OS — Chrome Web Store Publisher.

Empaqueta extension y sube a Chrome Web Store.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.ChromePublish")

EXTENSION_DIR = Path(__file__).resolve().parent
OUTPUT_ZIP = "dist/aura-chrome-extension-v1.2.0.zip"
THUMBNAIL = "assets/thumbnail_1280x800.png"


async def publish() -> Dict[str, Any]:
    """Empaqueta y prepara extension para Chrome Web Store."""
    logger.info("Publishing Chrome extension v1.2.0")

    manifest_path = EXTENSION_DIR / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {EXTENSION_DIR}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    version = manifest.get("version", "0.0.0")
    name = manifest.get("name", "AURA")

    zip_path = await _package_extension(manifest, version)
    thumbnail = await _generate_thumbnail()
    upload_info = await _prepare_upload(manifest, version)

    logger.info("Chrome extension packaged: %s", zip_path)

    return {
        "success": True,
        "name": name,
        "version": version,
        "zip_path": zip_path,
        "thumbnail": thumbnail,
        "upload_info": upload_info,
        "manifest": manifest,
        "timestamp": datetime.now().isoformat(),
    }


async def _package_extension(manifest: Dict[str, Any], version: str) -> str:
    """Crea zip de la extension."""
    os.makedirs("dist", exist_ok=True)
    zip_path = f"dist/aura-chrome-extension-v{version}.zip"

    files_to_include = [
        "manifest.json",
        "popup.html",
        "popup.js",
    ]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in files_to_include:
            filepath = EXTENSION_DIR / filename
            if filepath.exists():
                zf.write(filepath, filename)
                logger.debug("Added: %s", filename)
            else:
                logger.warning("Missing: %s", filename)

        for asset_dir in ["assets"]:
            asset_path = EXTENSION_DIR / asset_dir
            if asset_path.exists():
                for asset_file in asset_path.rglob("*"):
                    if asset_file.is_file():
                        arcname = f"{asset_file.relative_to(EXTENSION_DIR)}"
                        zf.write(asset_file, arcname)

    size_kb = os.path.getsize(zip_path) / 1024
    return zip_path


async def _generate_thumbnail() -> str:
    """Genera thumbnail 1280x800 para Chrome Web Store."""
    thumbnail_path = EXTENSION_DIR / "assets" / "thumbnail_1280x800.png"

    try:
        from PIL import Image
        img = Image.new("RGB", (1280, 800), color="#0f172a")
        draw = __import__("PIL.ImageDraw", fromlist=["Draw"]).Draw(img)
        try:
            font = __import__("PIL.ImageFont", fromlist=["truetype"]).truetype("arial.ttf", 60)
        except Exception:
            font = __import__("PIL.ImageFont", fromlist=["truetype"]).load_default()
        draw.text((640, 400), "AURA Assistant", fill="#38bdf8", font=font, anchor="mm")
        img.save(thumbnail_path)
        logger.info("Thumbnail generated: %s", thumbnail_path)
    except ImportError:
        with open(thumbnail_path, "w") as f:
            f.write("DUMMY_THUMBNAIL_1280x800")
        logger.warning("PIL not available, dummy thumbnail created")

    return str(thumbnail_path)


async def _prepare_upload(manifest: Dict[str, Any], version: str) -> Dict[str, Any]:
    """Prepara info para subida."""
    return {
        "extension_id": manifest.get("name", "AURA").lower().replace(" ", "-"),
        "version": version,
        "package_path": OUTPUT_ZIP,
        "chrome_web_store_url": "https://chrome.google.com/webstore/devconsole",
        "publish_command": f"chrome-webstore-publish --source {OUTPUT_ZIP} --client-id {manifest.get('name', '')}",
        "requires_admin_upload": False,
        "category": "Productivity",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio
    result = asyncio.run(publish())
    print(json.dumps(result, indent=2, default=str))
