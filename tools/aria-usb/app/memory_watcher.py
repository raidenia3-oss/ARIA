from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.memory_export import MemoryExporter, LongTermMemoryEntry, create_exporter
from app.obsidian_bridge import create_bridge, ObsidianBridge


class MemoryWatcher:
    """Watch ARIA long-term memory file and auto-export new entries to Obsidian vault."""

    def __init__(
        self,
        long_term_path: str,
        vault_path: str,
        render_api_url: str = "http://localhost:27123",
        memory_folder: str = "memory",
        drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
        poll_interval: float = 5.0,
        on_new_entries: Optional[Callable[[List[LongTermMemoryEntry]], None]] = None,
    ):
        self.long_term_path = Path(long_term_path)
        self.exporter = create_exporter(
            long_term_path=str(self.long_term_path),
            vault_path=vault_path,
            render_api_url=render_api_url,
            memory_folder=memory_folder,
            drive_folder_id=drive_folder_id,
        )
        self.poll_interval = poll_interval
        self.on_new_entries = on_new_entries
        self._known_ids: set = set()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._load_known_ids()

    def _load_known_ids(self) -> None:
        """Load existing entry IDs from long-term memory file."""
        if not self.long_term_path.exists():
            return
        try:
            with open(self.long_term_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._known_ids = {str(item.get("id", "")) for item in data if item.get("id")}
        except Exception:
            self._known_ids = set()

    def _get_new_entries(self) -> List[LongTermMemoryEntry]:
        """Get entries that weren't known before."""
        if not self.long_term_path.exists():
            return []
        try:
            with open(self.long_term_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        new_entries = []
        for item in data:
            eid = str(item.get("id", ""))
            if eid and eid not in self._known_ids:
                self._known_ids.add(eid)
                new_entries.append(LongTermMemoryEntry.from_dict(item))
        return new_entries

    def _poll(self) -> None:
        """Poll for new entries and export them."""
        while self._running:
            try:
                new_entries = self._get_new_entries()
                if new_entries:
                    for entry in new_entries:
                        note = self.exporter.entry_to_memory_note(entry)
                        self.exporter.bridge.write_memory_note(note)
                    if self.on_new_entries:
                        self.on_new_entries(new_entries)
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def start(self) -> None:
        """Start watching in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def export_existing(self, use_api: bool = False) -> Dict[str, Any]:
        """Export all existing entries (one-time)."""
        return self.exporter.export_to_vault(use_api=use_api)

    def check_once(self) -> int:
        """Check once for new entries and export them. Returns count of new entries."""
        new_entries = self._get_new_entries()
        if new_entries:
            for entry in new_entries:
                note = self.exporter.entry_to_memory_note(entry)
                self.exporter.bridge.write_memory_note(note)
            if self.on_new_entries:
                self.on_new_entries(new_entries)
        return len(new_entries)


class MemoryVaultManager:
    """High-level manager for ARIA memory vault operations."""

    def __init__(
        self,
        long_term_path: str,
        vault_path: str,
        render_api_url: str = "http://localhost:27123",
        memory_folder: str = "memory",
        drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
    ):
        self.exporter = create_exporter(
            long_term_path=long_term_path,
            vault_path=vault_path,
            render_api_url=render_api_url,
            memory_folder=memory_folder,
            drive_folder_id=drive_folder_id,
        )
        self.watcher = MemoryWatcher(
            long_term_path=long_term_path,
            vault_path=vault_path,
            render_api_url=render_api_url,
            memory_folder=memory_folder,
            drive_folder_id=drive_folder_id,
        )
        self.bridge = self.exporter.bridge

    def initial_export(self, use_api: bool = False) -> Dict[str, Any]:
        """Export all existing long-term memory to vault."""
        return self.exporter.export_to_vault(use_api=use_api)

    def start_auto_export(self) -> None:
        """Start auto-export watcher."""
        self.watcher.start()

    def stop_auto_export(self) -> None:
        """Stop auto-export watcher."""
        self.watcher.stop()

    def generate_dataview_queries(self) -> Dict[str, str]:
        """Return useful Dataview queries for the memory vault."""
        return {
            "all_facts": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" WHERE subtype = "fact" SORT created DESC\n```',
            "all_decisions": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" WHERE subtype = "decision" SORT created DESC\n```',
            "all_insights": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" WHERE subtype = "insight" SORT created DESC\n```',
            "by_source": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" GROUP BY source\n```',
            "by_phase": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" WHERE contains(tags, "phase-") SORT created DESC\n```',
            "high_confidence": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" WHERE confidence >= 0.8 SORT confidence DESC\n```',
            "recent_week": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" WHERE date(created) >= date(today) - dur(7 days) SORT created DESC\n```',
            "unlinked": '```dataview\nTABLE file.name, subtype, source, confidence, tags, created FROM "memory" WHERE length(links) = 0 SORT created DESC\n```',
        }

    def generate_memory_canvas(self, center_topic: str, query: str = "") -> str:
        """Generate a canvas from memory notes matching query."""
        if query:
            notes = self.bridge.search_memory(query=query, limit=20)
        else:
            notes = self.bridge.search_memory(limit=50)

        if not notes:
            return ""

        filename = f"memory-graph-{center_topic.lower().replace(' ', '-')}-{int(time.time())}"
        return self.bridge.generate_memory_canvas(center_topic, notes, filename)


def create_vault_manager(
    long_term_path: str,
    vault_path: str,
    render_api_url: str = "http://localhost:27123",
    memory_folder: str = "memory",
    drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
) -> MemoryVaultManager:
    return MemoryVaultManager(
        long_term_path=long_term_path,
        vault_path=vault_path,
        render_api_url=render_api_url,
        memory_folder=memory_folder,
        drive_folder_id=drive_folder_id,
    )