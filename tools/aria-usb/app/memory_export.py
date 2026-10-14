from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.obsidian_bridge import (
    MemoryNote,
    MemoryType,
    MemorySource,
    ObsidianBridge,
    create_bridge,
)


@dataclass
class LongTermMemoryEntry:
    id: str
    timestamp: str
    content: str
    meta: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LongTermMemoryEntry":
        return cls(
            id=str(data.get("id", "")),
            timestamp=str(data.get("timestamp", "")),
            content=str(data.get("content", "")),
            meta=data.get("meta", {}),
        )


class MemoryExporter:
    def __init__(
        self,
        long_term_path: str,
        vault_path: str,
        render_api_url: str = "http://localhost:27123",
        memory_folder: str = "memory",
        drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
    ):
        self.long_term_path = Path(long_term_path)
        self.bridge = create_bridge(
            vault_path=vault_path,
            render_api_url=render_api_url,
            memory_folder=memory_folder,
            drive_folder_id=drive_folder_id,
        )

    def load_long_term_memory(self) -> List[LongTermMemoryEntry]:
        if not self.long_term_path.exists():
            return []
        with open(self.long_term_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [LongTermMemoryEntry.from_dict(item) for item in raw]

    def entry_to_memory_note(self, entry: LongTermMemoryEntry) -> MemoryNote:
        meta = entry.meta
        subtype_str = meta.get("type", "fact")
        try:
            subtype = MemoryType(subtype_str)
        except ValueError:
            subtype = MemoryType.FACT

        source = MemorySource.SYSTEM_OBSERVATION
        if "source" in meta:
            try:
                source = MemorySource(meta["source"])
            except ValueError:
                pass

        confidence = float(meta.get("confidence", 0.8))
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        elif not isinstance(tags, list):
            tags = []

        phase = meta.get("phase")
        if phase is not None:
            tags.append(f"phase-{phase}")

        title = entry.content[:60].strip()
        if len(entry.content) > 60:
            title += "..."

        created = entry.timestamp
        updated = entry.timestamp

        return MemoryNote(
            type="memory",
            subtype=subtype,
            source=source,
            confidence=confidence,
            tags=tags,
            links=[],
            created=created,
            updated=updated,
            content=entry.content,
            title=title,
        )

    def export_to_vault(self, use_api: bool = False) -> Dict[str, Any]:
        entries = self.load_long_term_memory()
        results = {
            "total": len(entries),
            "exported": 0,
            "failed": 0,
            "details": [],
        }

        for entry in entries:
            note = self.entry_to_memory_note(entry)
            try:
                if use_api:
                    res = self.bridge.write_memory_note_via_api(note)
                    path = res.get("path", "unknown")
                else:
                    path = self.bridge.write_memory_note(note)
                results["exported"] += 1
                results["details"].append(
                    {"id": entry.id, "path": path, "status": "ok"}
                )
            except Exception as e:
                results["failed"] += 1
                results["details"].append(
                    {"id": entry.id, "error": str(e), "status": "error"}
                )

        return results

    def export_to_vault_and_sync(
        self, use_api: bool = False, sync_to_drive: bool = False
    ) -> Dict[str, Any]:
        export_results = self.export_to_vault(use_api=use_api)
        if sync_to_drive:
            sync_results = self.bridge.sync_to_drive()
            export_results["drive_sync"] = sync_results
        return export_results


def create_exporter(
    long_term_path: str,
    vault_path: str,
    render_api_url: str = "http://localhost:27123",
    memory_folder: str = "memory",
    drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
) -> MemoryExporter:
    return MemoryExporter(
        long_term_path=long_term_path,
        vault_path=vault_path,
        render_api_url=render_api_url,
        memory_folder=memory_folder,
        drive_folder_id=drive_folder_id,
    )