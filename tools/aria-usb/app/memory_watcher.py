from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

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

    def extract_memory_links(self, notes: Optional[List[Dict[str, Any]]] = None, keyword_threshold: int = 3) -> Dict[str, List[str]]:
        """Extract bidirectional links between memory notes based on content overlap.
        
        Returns dict of note_path -> list of linked note_paths.
        """
        if notes is None:
            # Try Render API first, fall back to filesystem
            try:
                notes = self.bridge.search_memory(limit=200)
            except Exception:
                notes = self._scan_memory_files()
        
        # Build content index
        note_index: Dict[str, Dict[str, Any]] = {}
        for note in notes:
            path = note.get("file.path", "")
            content = note.get("content", "") or note.get("file.name", "")
            if path and content:
                note_index[path] = {
                    "content": content.lower(),
                    "tags": set(note.get("tags", []) if isinstance(note.get("tags"), list) else []),
                    "title": note.get("file.name", ""),
                }
        
        links: Dict[str, List[str]] = {path: [] for path in note_index}
        
        # Find links based on:
        # 1. Shared tags
        # 2. Content keyword overlap
        # 3. Explicit [[wiki-links]] in content
        paths = list(note_index.keys())
        for i, path_a in enumerate(paths):
            data_a = note_index[path_a]
            for path_b in paths[i+1:]:
                data_b = note_index[path_b]
                
                link_reasons = []
                
                # Shared tags
                shared_tags = data_a["tags"] & data_b["tags"]
                if shared_tags:
                    link_reasons.append(f"tags:{','.join(shared_tags)}")
                
                # Content keyword overlap (significant words)
                words_a = set(re.findall(r'\b\w{4,}\b', data_a["content"]))
                words_b = set(re.findall(r'\b\w{4,}\b', data_b["content"]))
                overlap = words_a & words_b
                if len(overlap) >= keyword_threshold:
                    link_reasons.append(f"keywords:{len(overlap)}")
                
                # Explicit wiki-links
                if f"[[{data_b['title']}]]" in data_a["content"] or f"[[{data_a['title']}]]" in data_b["content"]:
                    link_reasons.append("wikilink")
                
                if link_reasons:
                    links[path_a].append(path_b)
                    links[path_b].append(path_a)
        
        return links

    def _scan_memory_files(self) -> List[Dict[str, Any]]:
        """Scan memory folder directly for notes (fallback when Render API unavailable)."""
        notes = []
        memory_dir = os.path.join(self.bridge.vault_path, self.bridge.memory_folder)
        if not os.path.exists(memory_dir):
            return notes
        
        import yaml
        for root, dirs, files in os.walk(memory_dir):
            for file in files:
                if not file.endswith(".md"):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.bridge.vault_path)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Parse frontmatter
                    frontmatter = {}
                    body = content
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            try:
                                frontmatter = yaml.safe_load(parts[1]) or {}
                            except Exception:
                                pass
                            body = parts[2].strip()
                    
                    notes.append({
                        "file.path": rel_path.replace("\\", "/"),
                        "file.name": file[:-3],
                        "content": body,
                        "subtype": frontmatter.get("subtype", "fact"),
                        "source": frontmatter.get("source", "system_observation"),
                        "confidence": frontmatter.get("confidence", 0.8),
                        "tags": frontmatter.get("tags", []),
                        "links": frontmatter.get("links", []),
                    })
                except Exception:
                    pass
        return notes

    def write_memory_links(self, links: Dict[str, List[str]]) -> int:
        """Update memory notes with extracted links in frontmatter."""
        updated = 0
        for path, linked_paths in links.items():
            if not linked_paths:
                continue
            try:
                full_path = os.path.join(self.bridge.vault_path, path)
                if not os.path.exists(full_path):
                    continue
                
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Parse frontmatter
                if not content.startswith("---"):
                    continue
                parts = content.split("---", 2)
                if len(parts) < 3:
                    continue
                
                frontmatter = parts[1].strip()
                body = parts[2].strip()
                
                # Add links to frontmatter
                link_lines = "\n".join([f"  - {lp}" for lp in sorted(set(linked_paths))])
                if "links:" in frontmatter:
                    # Replace existing links
                    new_fm = re.sub(r'links:.*?(?=\n\w+:|\n---|\Z)', f'links:\n{link_lines}\n', frontmatter, flags=re.DOTALL)
                else:
                    # Add links section
                    new_fm = frontmatter + f"\nlinks:\n{link_lines}\n"
                
                new_content = f"---\n{new_fm}---\n\n{body}"
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                updated += 1
            except Exception:
                pass
        return updated

    def generate_canvas_from_template(self, template_name: str, context: Dict[str, Any], template_dir: Optional[str] = None) -> str:
        """Generate a canvas from a template file with context variables."""
        if template_dir:
            template_path = Path(template_dir) / f"{template_name}.canvas"
        else:
            template_path = Path(__file__).parent.parent / "templates" / "canvas" / f"{template_name}.canvas"
        if not template_path.exists():
            return ""
        
        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)
        
        # Replace template variables in nodes
        def replace_vars(obj: Any) -> Any:
            if isinstance(obj, str):
                for key, value in context.items():
                    obj = obj.replace(f"{{{{{key}}}}}", str(value))
                return obj
            elif isinstance(obj, dict):
                return {k: replace_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_vars(v) for v in obj]
            return obj
        
        template = replace_vars(template)
        
        # Save to vault
        filename = f"{template_name}-{int(time.time())}"
        rel_path = os.path.join("canvas", f"{filename}.canvas")
        full_path = os.path.join(self.bridge.vault_path, rel_path)
        
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        
        return rel_path

    def generate_vault_index(self) -> str:
        """Generate a vault index/dashboard page."""
        # Try Render API first, fall back to filesystem
        try:
            notes = self.bridge.search_memory(limit=500)
        except Exception:
            notes = self._scan_memory_files()
        
        # Stats
        total = len(notes)
        by_subtype: Dict[str, int] = {}
        by_source: Dict[str, int] = {}
        by_confidence: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        phases: Set[str] = set()
        
        for note in notes:
            subtype = note.get("subtype", "unknown")
            by_subtype[subtype] = by_subtype.get(subtype, 0) + 1
            
            source = note.get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + 1
            
            conf = float(note.get("confidence", 0))
            if conf >= 0.8:
                by_confidence["high"] += 1
            elif conf >= 0.5:
                by_confidence["medium"] += 1
            else:
                by_confidence["low"] += 1
            
            tags = note.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if tag.startswith("phase-"):
                        phases.add(tag)
        
        index_content = f"""---
type: index
title: ARIA Memory Vault Index
created: {datetime.utcnow().isoformat()}Z
---

# ARIA Memory Vault 📚

> Auto-generated index of all memory notes in this vault.

## 📊 Overview

| Metric | Value |
|--------|-------|
| Total Notes | {total} |
| High Confidence (≥0.8) | {by_confidence['high']} |
| Medium Confidence (0.5-0.8) | {by_confidence['medium']} |
| Low Confidence (<0.5) | {by_confidence['low']} |

## 📂 By Type

| Subtype | Count |
|---------|-------|
"""
        for subtype, count in sorted(by_subtype.items(), key=lambda x: -x[1]):
            index_content += f"| {subtype} | {count} |\n"
        
        index_content += "\n## 🔍 By Source\n\n| Source | Count |\n|--------|-------|\n"
        for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
            index_content += f"| {source} | {count} |\n"
        
        index_content += f"\n## 🏷️ Phases Detected\n\n{', '.join(sorted(phases)) if phases else 'None'}\n"
        
        index_content += "\n## 🔗 Quick Links\n\n"
        for name, query in self.generate_dataview_queries().items():
            index_content += f"- [[{name}]] — {name.replace('_', ' ').title()}\n"
        
        index_content += "\n## 📊 Canvases\n\n"
        for template in ["topic-center", "timeline", "source-hub", "phase-overview", "confidence-levels"]:
            index_content += f"- `canvas/{template}.canvas` — {template.replace('-', ' ').title()}\n"
        
        # Save index
        rel_path = "INDEX.md"
        full_path = os.path.join(self.bridge.vault_path, rel_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(index_content)
        
        return rel_path


from datetime import datetime


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