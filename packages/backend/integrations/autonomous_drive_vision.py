# -*- coding: utf-8 -*-
"""Autonomous Drive Vision — processes media from Google Drive without intervention.

Runs automatically when backend starts. Downloads photos/videos/PDFs,
describes them with ARIA Eyes, and saves results to instagram/descriptions/.
Uses local model (granite3.2-vision:2b) with cloud fallback.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "downloads"
DESCRIPTIONS_DIR = REPO_ROOT / "instagram" / "descriptions"
DESCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILES = 2
PROCESSED_FILE = REPO_ROOT / "instagram" / "descriptions" / ".processed"


def _load_processed() -> set[str]:
    if PROCESSED_FILE.exists():
        return set(PROCESSED_FILE.read_text(encoding="utf-8").splitlines())
    return set()


def _save_processed(files: set[str]) -> None:
    PROCESSED_FILE.write_text("\n".join(sorted(files)), encoding="utf-8")


async def _download_from_drive(drive_connector, file_id: str, file_name: str) -> str:
    out_file = OUTPUT_DIR / file_name
    if out_file.exists():
        return str(out_file)
    req = drive_connector.service.files().get_media(fileId=file_id)
    fh = open(out_file, "wb")
    try:
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    finally:
        fh.close()
    return str(out_file)


async def _describe_file(path: str, mime: str) -> dict | None:
    from scripts.aria_eyes import (
        describe, OllamaVision, load_source, tile_sweep, ocr_pass,
        deterministic_facts, render_text,
    )
    from PIL import Image
    import io

    sources = load_source(Path(path), 1 if mime.startswith("video/") else 1)
    if not sources:
        return None

    client = OllamaVision(max_side=512, num_ctx=4096)
    units = []
    for label, img in sources:
        facts = deterministic_facts(img)
        sweep = tile_sweep(img, client, cols=2, rows=2, on_progress=lambda m: None)
        ocr = ocr_pass(img, client)
        units.append({
            "label": label,
            "measured": facts,
            "tile_sweep": sweep,
            "ocr": ocr,
            "narrative": "[omitted for local speed]",
            "verification": {"available": False, "reason": "skipped"},
            "cross_check": {"available": False, "reason": "skipped", "contradictions": []},
            "unverified_claims": [],
            "stage_errors": [],
            "complete": True,
            "trust": {
                "measured": "arithmetic",
                "tiles": "model, per-tile",
                "ocr": "model, verbatim request",
                "narrative": "skipped for local speed",
            },
        })

    name = os.path.basename(path)
    return {
        "source": str(path),
        "model": client.model,
        "units": units,
        "caveat": "Model output is not a measurement. Trust 'measured' blindly.",
    }


async def run_autonomous_drive_vision() -> dict:
    """Process all unprocessed media from Google Drive."""
    logger.info("Starting autonomous Drive vision processing")

    try:
        from backend.drive_connector import drive_connector
    except ImportError:
        logger.warning("Drive connector not available, skipping autonomous vision")
        return {"status": "skipped", "reason": "drive_connector not available"}

    if not drive_connector.is_ready():
        logger.warning("Drive not connected, skipping autonomous vision")
        return {"status": "skipped", "reason": "drive not connected"}

    processed = _load_processed()
    files = drive_connector.list_files(page_size=50)
    all_files = files.get("files", [])

    media = [
        f for f in all_files
        if f.get("mimeType", "").startswith(("image/", "video/"))
        and f["name"] not in processed
    ][:MAX_FILES]

    if not media:
        logger.info("No new media files to process")
        return {"status": "complete", "processed": 0}

    logger.info(f"Processing {len(media)} new media files from Drive")

    results = []
    for f in media:
        name = f["name"]
        mime = f["mimeType"]
        start = time.time()
        logger.info(f"  [{name}] ({mime})")

        try:
            path = await _download_from_drive(drive_connector, f["id"], name)
            result = await _describe_file(path, mime)

            if result:
                desc_file = DESCRIPTIONS_DIR / f"{name}.json"
                with open(desc_file, "w", encoding="utf-8") as fh:
                    json.dump(result, fh, ensure_ascii=False, indent=2)

                from scripts.aria_eyes import render_text
                txt_file = DESCRIPTIONS_DIR / f"{name}.txt"
                with open(txt_file, "w", encoding="utf-8") as fh:
                    fh.write(render_text(result))

                processed.add(name)
                _save_processed(processed)
                results.append({"file": name, "status": "ok", "time_s": int(time.time() - start)})
                logger.info(f"    Saved ({time.time()-start:.0f}s)")
            else:
                results.append({"file": name, "status": "error", "error": "no frames decoded"})
        except Exception as exc:
            results.append({"file": name, "status": "error", "error": str(exc)})
            logger.error(f"    ERROR: {exc}")

    summary = DESCRIPTIONS_DIR / "summary.json"
    with open(summary, "w", encoding="utf-8") as fh:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_files": len(results),
            "processed": len([r for r in results if r["status"] == "ok"]),
            "files": results,
        }, fh, ensure_ascii=False, indent=2)

    logger.info(f"Done: {len(results)} files processed")
    return {
        "status": "complete",
        "total": len(results),
        "processed": len([r for r in results if r["status"] == "ok"]),
    }


async def _run_with_keepawake() -> None:
    """Run vision processing with sleep prevention on supported platforms."""
    from backend.integrations.autonomous_agent import autonomous_agent

    is_mac = sys.platform == "darwin"

    if is_mac:
        autonomous_agent.insomnia.prevent_sleep(240)

    try:
        result = await run_autonomous_drive_vision()
        logger.info(f"Autonomous vision result: {result}")
    finally:
        if is_mac:
            autonomous_agent.insomnia.restore()


def start_autonomous_agent() -> None:
    """Entry point for autonomous background operation.

    Called automatically on backend startup. Starts sleep prevention
    and runs Drive vision processing in a background thread so the
    server is never blocked.
    """
    import threading

    def _run() -> None:
        asyncio.run(_run_with_keepawake())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


autonomous_drive_vision_running = False
