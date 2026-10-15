import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.policy import Policy, AccessLevel, PathRisk, DEFAULT_POLICY
from app.vault import Vault, encrypt_blob, decrypt_blob
from app.core import create_registry, ToolResult, ToolStatus
from app.llm_local import LLMLocalClient
from app.memory_export import MemoryExporter, LongTermMemoryEntry
from app.memory_watcher import MemoryWatcher, MemoryVaultManager, create_vault_manager
from app.obsidian_bridge import MemoryNote, MemoryType, MemorySource


class TestPolicy:
    def setup_method(self):
        self.policy = Policy()
        self.policy.fs_roots = [str(Path.cwd())]
        self.policy.add_rule("work/**", AccessLevel.READ)
        self.policy.add_rule("work/**", AccessLevel.WRITE)

    def test_allow_work_read(self):
        allowed, reason = self.policy.check_path("work/file.txt", self.policy.fs_roots, PathRisk.READ)
        assert allowed
        assert "read" in reason.lower() or "meta" in reason.lower()

    def test_allow_work_write(self):
        allowed, reason = self.policy.check_path("work/file.txt", self.policy.fs_roots, PathRisk.WRITE)
        assert allowed

    def test_deny_outside_roots(self):
        allowed, reason = self.policy.check_path("../secret.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed
        assert "outside" in reason.lower()

    def test_deny_traversal(self):
        allowed, reason = self.policy.check_path("work/../../etc/passwd", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_deny_ads(self):
        allowed, reason = self.policy.check_path("work/file.txt:stream", self.policy.fs_roots, PathRisk.READ)
        assert not allowed
        assert "ads" in reason.lower()

    def test_deny_reserved_name(self):
        allowed, reason = self.policy.check_path("work/CON.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_sensitive_location_deny(self):
        allowed, reason = self.policy.check_path("C:\\Users\\test\\AppData\\Local\\file.txt", ["C:\\"], PathRisk.READ)
        assert not allowed

    def test_secret_file_meta_only(self):
        allowed, reason = self.policy.check_path("work/secret.key", self.policy.fs_roots, PathRisk.READ)
        assert allowed
        assert "meta" in reason.lower()

    def test_media_file_meta_default(self):
        allowed, reason = self.policy.check_path("work/photo.jpg", self.policy.fs_roots, PathRisk.READ)
        assert allowed
        assert "meta" in reason.lower()

    def test_media_override_allows_read(self):
        self.policy.add_rule("work/media/**", AccessLevel.READ, media_override=True)
        allowed, reason = self.policy.check_path("work/media/photo.jpg", self.policy.fs_roots, PathRisk.READ)
        assert allowed

    def test_deny_by_default_unknown(self):
        allowed, reason = self.policy.check_path("work/unknown.xyz", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_case_insensitive(self):
        allowed, reason = self.policy.check_path("WORK/FILE.TXT", self.policy.fs_roots, PathRisk.READ)
        assert allowed

    def test_unc_path_denied(self):
        allowed, reason = self.policy.check_path("\\\\server\\share\\file.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_long_path_prefix(self):
        allowed, reason = self.policy.check_path("\\\\?\\C:\\work\\file.txt", self.policy.fs_roots, PathRisk.READ)
        assert not allowed

    def test_list_visible_filters_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            work.mkdir()
            (work / "visible.txt").write_text("x")
            (work / ".hidden").write_text("x")
            self.policy.fs_roots = [tmp]
            visible = self.policy.list_visible(str(work))
            assert "visible.txt" in visible
            assert ".hidden" not in visible


class TestVault:
    def test_roundtrip(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            vault = Vault(path)
            data = b"secret data"
            vault.create("passphrase123", data)
            result = vault.open("passphrase123")
            assert result == data
            vault.close()
        finally:
            os.unlink(path)

    def test_wrong_passphrase_fails(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            vault = Vault(path)
            vault.create("correct", b"data")
            with pytest.raises(ValueError, match="passphrase incorrecta"):
                vault.open("wrong")
        finally:
            os.unlink(path)

    def test_tampered_file_fails(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            vault = Vault(path)
            vault.create("pass", b"data")
            with open(path, "rb") as f:
                data = f.read()
            tampered = data.replace(b"ct", b"xx", 1)
            with open(path, "wb") as f:
                f.write(tampered)
            with pytest.raises(ValueError, match="passphrase incorrecta|manipulado"):
                vault.open("pass")
        finally:
            os.unlink(path)

    def test_salt_unique_per_creation(self):
        with tempfile.NamedTemporaryFile(delete=False) as f1, tempfile.NamedTemporaryFile(delete=False) as f2:
            path1, path2 = f1.name, f2.name
        try:
            Vault(path1).create("same", b"data")
            Vault(path2).create("same", b"data")
            with open(path1, "rb") as f:
                blob1 = json.loads(f.read())
            with open(path2, "rb") as f:
                blob2 = json.loads(f.read())
            assert blob1["salt"] != blob2["salt"]
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestCore:
    def setup_method(self):
        self.policy = Policy()
        self.policy.fs_roots = [str(Path.cwd())]
        self.policy.add_rule("work/**", AccessLevel.READ)
        self.policy.add_rule("work/**", AccessLevel.WRITE)
        self.registry = create_registry(self.policy)

    def test_register_and_run_ok(self):
        @self.registry.register("echo", {"type": "object", "properties": {"msg": {"type": "string"}}}, PathRisk.READ, [])
        def echo(msg: str) -> ToolResult:
            return ToolResult.ok("echo", {"echo": msg})

        result = self.registry.run("echo", {"msg": "hola"}, self.policy.fs_roots)
        assert result.status == ToolStatus.OK
        assert result.result == {"echo": "hola"}

    def test_invalid_return_type_fails(self):
        @self.registry.register("bad", {"type": "object"}, PathRisk.READ, [])
        def bad() -> str:
            return "not a ToolResult"

        result = self.registry.run("bad", {}, self.policy.fs_roots)
        assert result.status == ToolStatus.FAILED
        assert "tipo de retorno invalido" in result.error

    def test_policy_deny_on_path_arg(self):
        @self.registry.register("read_file", {"type": "object", "properties": {"path": {"type": "string"}}}, PathRisk.READ, ["path"])
        def read_file(path: str) -> ToolResult:
            return ToolResult.ok("read_file", {"path": path})

        result = self.registry.run("read_file", {"path": "../secret.txt"}, self.policy.fs_roots)
        assert result.status == ToolStatus.FAILED
        assert "policy deny" in result.error

    def test_unknown_tool_fails(self):
        result = self.registry.run("nonexistent", {}, self.policy.fs_roots)
        assert result.status == ToolStatus.FAILED
        assert "not found" in result.error


class TestLLMLocalClient:
    def test_schema_validation_ok(self):
        client = LLMLocalClient("http://127.0.0.1:9999")
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
        valid_json = '{"answer": "42"}'
        result = client._validate_json(valid_json, schema)
        assert json.loads(result) == {"answer": "42"}

    def test_schema_validation_fail_missing_field(self):
        client = LLMLocalClient("http://127.0.0.1:9999")
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
        invalid_json = '{}'
        with pytest.raises(ValueError, match="JSON no cumple schema"):
            client._validate_json(invalid_json, schema)

    def test_invalid_json_fails(self):
        client = LLMLocalClient("http://127.0.0.1:9999")
        schema = {"type": "object"}
        with pytest.raises(ValueError, match="no es JSON"):
            client._validate_json("not json", schema)


class TestCanaries:
    def test_canary_outside_roots_not_accessible(self):
        policy = Policy()
        policy.fs_roots = [str(Path.cwd())]
        policy.add_rule("work/**", AccessLevel.READ)

        with tempfile.TemporaryDirectory() as tmp:
            canary = Path(tmp) / "canary_secret.txt"
            canary.write_text("SECRET_CANARY_CONTENT")
            allowed, _ = policy.check_path(str(canary), policy.fs_roots, PathRisk.READ)
            assert not allowed

    def test_canary_not_listed(self):
        policy = Policy()
        policy.fs_roots = [str(Path.cwd())]
        policy.add_rule("work/**", AccessLevel.READ)

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            work.mkdir()
            (work / "normal.txt").write_text("ok")
            canary = Path(tmp) / "canary.txt"
            canary.write_text("SECRET")
            policy.fs_roots = [tmp]
            visible = policy.list_visible(str(work))
            assert "normal.txt" in visible
            assert "canary.txt" not in visible


class TestMemoryExport:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vault_dir = os.path.join(self.tmpdir, "vault")
        self.memory_dir = os.path.join(self.vault_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        self.long_term_path = os.path.join(self.tmpdir, "long_term.json")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_long_term(self, entries: List[Dict[str, Any]]) -> None:
        with open(self.long_term_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def test_load_long_term_memory(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Test fact", "meta": {"type": "fact"}},
            {"id": "2", "timestamp": "2026-01-02T00:00:00Z", "content": "Test decision", "meta": {"type": "decision"}},
        ]
        self._write_long_term(entries)

        exporter = MemoryExporter(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        loaded = exporter.load_long_term_memory()

        assert len(loaded) == 2
        assert loaded[0].id == "1"
        assert loaded[0].content == "Test fact"
        assert loaded[0].meta["type"] == "fact"
        assert loaded[1].meta["type"] == "decision"

    def test_load_empty_long_term(self):
        exporter = MemoryExporter(
            long_term_path=os.path.join(self.tmpdir, "nonexistent.json"),
            vault_path=self.vault_dir,
        )
        loaded = exporter.load_long_term_memory()
        assert loaded == []

    def test_entry_to_memory_note_fact(self):
        entry = LongTermMemoryEntry(
            id="test-1",
            timestamp="2026-01-01T00:00:00Z",
            content="This is a test fact",
            meta={"type": "fact", "confidence": 0.9, "tags": ["test", "important"]},
        )

        exporter = MemoryExporter(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        note = exporter.entry_to_memory_note(entry)

        assert isinstance(note, MemoryNote)
        assert note.subtype == MemoryType.FACT
        assert note.source == MemorySource.SYSTEM_OBSERVATION
        assert note.confidence == 0.9
        assert "test" in note.tags
        assert "important" in note.tags
        assert note.content == "This is a test fact"
        assert note.title == "This is a test fact"

    def test_entry_to_memory_note_decision(self):
        entry = LongTermMemoryEntry(
            id="test-2",
            timestamp="2026-01-01T00:00:00Z",
            content="Decision made",
            meta={"type": "decision", "phase": 3},
        )

        exporter = MemoryExporter(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        note = exporter.entry_to_memory_note(entry)

        assert note.subtype == MemoryType.DECISION
        assert "phase-3" in note.tags

    def test_entry_to_memory_note_unknown_type_defaults_to_fact(self):
        entry = LongTermMemoryEntry(
            id="test-3",
            timestamp="2026-01-01T00:00:00Z",
            content="Unknown type content",
            meta={"type": "unknown_type"},
        )

        exporter = MemoryExporter(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        note = exporter.entry_to_memory_note(entry)

        assert note.subtype == MemoryType.FACT

    def test_entry_to_memory_note_long_content_truncates_title(self):
        entry = LongTermMemoryEntry(
            id="test-4",
            timestamp="2026-01-01T00:00:00Z",
            content="A" * 100,
            meta={"type": "fact"},
        )

        exporter = MemoryExporter(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        note = exporter.entry_to_memory_note(entry)

        assert len(note.title) == 63
        assert note.title.endswith("...")

    def test_export_to_vault_creates_files(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Fact one", "meta": {"type": "fact"}},
            {"id": "2", "timestamp": "2026-01-02T00:00:00Z", "content": "Fact two", "meta": {"type": "insight"}},
        ]
        self._write_long_term(entries)

        exporter = MemoryExporter(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        results = exporter.export_to_vault(use_api=False)

        assert results["total"] == 2
        assert results["exported"] == 2
        assert results["failed"] == 0
        assert len(results["details"]) == 2

        files = list(Path(self.memory_dir).glob("*.md"))
        assert len(files) == 2

        for f in files:
            content = f.read_text(encoding="utf-8")
            assert content.startswith("---")
            assert "type: memory" in content
            assert "subtype:" in content

    def test_export_to_vault_preserves_frontmatter(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Test content", "meta": {"type": "fact", "confidence": 0.7, "tags": ["tag1"]}},
        ]
        self._write_long_term(entries)

        exporter = MemoryExporter(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        exporter.export_to_vault(use_api=False)

        files = list(Path(self.memory_dir).glob("*.md"))
        content = files[0].read_text(encoding="utf-8")

        assert "subtype: fact" in content
        assert "confidence: 0.7" in content
        assert "tags:" in content
        assert "tag1" in content
        assert "source: system_observation" in content
        assert "Test content" in content


class TestMemoryWatcher:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vault_dir = os.path.join(self.tmpdir, "vault")
        self.memory_dir = os.path.join(self.vault_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        self.long_term_path = os.path.join(self.tmpdir, "long_term.json")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_long_term(self, entries: List[Dict[str, Any]]) -> None:
        with open(self.long_term_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def test_watcher_loads_known_ids(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Fact one", "meta": {"type": "fact"}},
            {"id": "2", "timestamp": "2026-01-02T00:00:00Z", "content": "Fact two", "meta": {"type": "fact"}},
        ]
        self._write_long_term(entries)

        watcher = MemoryWatcher(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )

        assert "1" in watcher._known_ids
        assert "2" in watcher._known_ids
        assert len(watcher._known_ids) == 2

    def test_watcher_detects_new_entries(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Fact one", "meta": {"type": "fact"}},
        ]
        self._write_long_term(entries)

        watcher = MemoryWatcher(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )

        # Add new entry
        entries.append({"id": "2", "timestamp": "2026-01-02T00:00:00Z", "content": "Fact two", "meta": {"type": "fact"}})
        self._write_long_term(entries)

        new_entries = watcher._get_new_entries()

        assert len(new_entries) == 1
        assert new_entries[0].id == "2"
        assert new_entries[0].content == "Fact two"

    def test_watcher_check_once_exports_new(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Fact one", "meta": {"type": "fact"}},
        ]
        self._write_long_term(entries)

        watcher = MemoryWatcher(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )

        # Add new entry
        entries.append({"id": "2", "timestamp": "2026-01-02T00:00:00Z", "content": "Fact two", "meta": {"type": "decision"}})
        self._write_long_term(entries)

        count = watcher.check_once()

        assert count == 1
        files = list(Path(self.memory_dir).glob("*.md"))
        assert len(files) == 1  # Only new entry exported

        # Check the new file has correct frontmatter
        for f in files:
            content = f.read_text(encoding="utf-8")
            if "Fact two" in content:
                assert "subtype: decision" in content

    def test_vault_manager_initial_export(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Fact one", "meta": {"type": "fact"}},
            {"id": "2", "timestamp": "2026-01-02T00:00:00Z", "content": "Fact two", "meta": {"type": "insight"}},
        ]
        self._write_long_term(entries)

        mgr = create_vault_manager(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )

        results = mgr.initial_export(use_api=False)

        assert results["total"] == 2
        assert results["exported"] == 2
        files = list(Path(self.memory_dir).glob("*.md"))
        assert len(files) == 2

    def test_vault_manager_generate_dataview_queries(self):
        entries = [
            {"id": "1", "timestamp": "2026-01-01T00:00:00Z", "content": "Fact one", "meta": {"type": "fact"}},
        ]
        self._write_long_term(entries)

        mgr = create_vault_manager(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )

        queries = mgr.generate_dataview_queries()

        assert "all_facts" in queries
        assert "all_decisions" in queries
        assert "all_insights" in queries
        assert "by_source" in queries
        assert "by_phase" in queries
        assert "high_confidence" in queries
        assert "recent_week" in queries
        assert "unlinked" in queries

        # Check format is proper markdown code block
        for q in queries.values():
            assert q.startswith("```dataview")
            assert q.endswith("```")


class TestMemoryWatcherPhase6:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vault_dir = os.path.join(self.tmpdir, "vault")
        self.memory_dir = os.path.join(self.vault_dir, "memory")
        self.canvas_dir = os.path.join(self.vault_dir, "canvas")
        self.templates_dir = os.path.join(self.tmpdir, "templates", "canvas")
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.canvas_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
        self.long_term_path = os.path.join(self.tmpdir, "long_term.json")

        # Create template files
        self._create_templates()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_templates(self) -> None:
        templates = {
            "topic-center.canvas": json.dumps({
                "nodes": [{"id": "center-topic", "type": "text", "x": 0, "y": 0, "width": 300, "height": 100, "text": "# {{TOPIC}}", "color": "#4a90d9"}],
                "edges": []
            }),
            "timeline.canvas": json.dumps({
                "nodes": [
                    {"id": "timeline-start", "type": "text", "x": -600, "y": 0, "width": 200, "height": 80, "text": "📅 **Timeline Start**\n{{START_DATE}}", "color": "#2ecc71"},
                    {"id": "timeline-end", "type": "text", "x": 600, "y": 0, "width": 200, "height": 80, "text": "📅 **Timeline End**\n{{END_DATE}}", "color": "#e74c3c"}
                ],
                "edges": [{"id": "timeline-edge", "from": "timeline-start", "to": "timeline-end", "label": "{{ENTRY_COUNT}} entries"}]
            }),
        }
        for name, content in templates.items():
            with open(os.path.join(self.templates_dir, name), "w", encoding="utf-8") as f:
                f.write(content)

    def _write_memory_notes(self, notes: List[Dict[str, Any]]) -> None:
        """Write memory note files directly to vault (simulating export)."""
        import yaml
        for note in notes:
            frontmatter = {
                "type": "memory",
                "subtype": note.get("subtype", "fact"),
                "source": note.get("source", "system_observation"),
                "confidence": note.get("confidence", 0.8),
                "tags": note.get("tags", []),
                "links": note.get("links", []),
                "created": note.get("created", "2026-01-01T00:00:00Z"),
                "updated": note.get("updated", "2026-01-01T00:00:00Z"),
            }
            fm_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
            content = f"---\n{fm_yaml}\n---\n\n# {note['title']}\n\n{note['content']}"
            filename = f"{note['id']}-{note['title']}.md"
            path = os.path.join(self.memory_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    def _write_long_term(self, entries: List[Dict[str, Any]]) -> None:
        with open(self.long_term_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def test_extract_memory_links_shared_tags(self):
        notes = [
            {"id": "1", "title": "Fact One", "content": "Content about ARIA", "subtype": "fact", "tags": ["aria", "phase-1"], "source": "system_observation", "confidence": 0.9, "created": "2026-01-01T00:00:00Z"},
            {"id": "2", "title": "Fact Two", "content": "More ARIA content", "subtype": "fact", "tags": ["aria", "phase-2"], "source": "system_observation", "confidence": 0.8, "created": "2026-01-02T00:00:00Z"},
            {"id": "3", "title": "Unrelated", "content": "Different topic", "subtype": "fact", "tags": ["other"], "source": "system_observation", "confidence": 0.7, "created": "2026-01-03T00:00:00Z"},
        ]
        self._write_memory_notes(notes)

        mgr = create_vault_manager(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        # Override templates path for test
        mgr.bridge.vault_path = self.vault_dir

        links = mgr.extract_memory_links()

        # Note 1 and 2 should be linked (shared tag "aria")
        path1 = next(p for p in links if "Fact One" in p)
        path2 = next(p for p in links if "Fact Two" in p)
        path3 = next(p for p in links if "Unrelated" in p)

        assert path2 in links[path1]
        assert path1 in links[path2]
        assert path3 not in links[path1]
        assert path3 not in links[path2]

    def test_extract_memory_links_keyword_overlap(self):
        notes = [
            {"id": "1", "title": "Python Testing", "content": "Python testing with pytest and unittest framework for python code debugging", "subtype": "fact", "tags": [], "source": "system_observation", "confidence": 0.9, "created": "2026-01-01T00:00:00Z"},
            {"id": "2", "title": "Python Debugging", "content": "Debugging python code using pdb and logging for python projects testing", "subtype": "fact", "tags": [], "source": "system_observation", "confidence": 0.8, "created": "2026-01-02T00:00:00Z"},
            {"id": "3", "title": "JavaScript Basics", "content": "JavaScript variables functions and objects for web development", "subtype": "fact", "tags": [], "source": "system_observation", "confidence": 0.7, "created": "2026-01-03T00:00:00Z"},
        ]
        self._write_memory_notes(notes)

        mgr = create_vault_manager(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        mgr.bridge.vault_path = self.vault_dir

        links = mgr.extract_memory_links()

        path1 = next(p for p in links if "Python Testing" in p)
        path2 = next(p for p in links if "Python Debugging" in p)
        path3 = next(p for p in links if "JavaScript Basics" in p)

        # Python notes should be linked (shared keywords: python, code, debugging, testing)
        assert path2 in links[path1]
        assert path1 in links[path2]
        # JavaScript should not be linked
        assert path3 not in links[path1]
        assert path3 not in links[path2]

    def test_write_memory_links_updates_frontmatter(self):
        notes = [
            {"id": "1", "title": "Note A", "content": "Content A", "subtype": "fact", "tags": ["tag1"], "source": "system_observation", "confidence": 0.9, "created": "2026-01-01T00:00:00Z"},
            {"id": "2", "title": "Note B", "content": "Content B", "subtype": "fact", "tags": ["tag1"], "source": "system_observation", "confidence": 0.8, "created": "2026-01-02T00:00:00Z"},
        ]
        self._write_memory_notes(notes)

        mgr = create_vault_manager(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        mgr.bridge.vault_path = self.vault_dir

        links = mgr.extract_memory_links()
        updated = mgr.write_memory_links(links)

        assert updated == 2

        # Verify links written to frontmatter
        for f in Path(self.memory_dir).glob("*.md"):
            content = f.read_text(encoding="utf-8")
            assert "links:" in content
            # Should contain link to the other note
            other = "Note B" if "Note A" in content else "Note A"
            assert other in content

    def test_generate_canvas_from_template(self):
        self._write_long_term([])

        mgr = create_vault_manager(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        mgr.bridge.vault_path = self.vault_dir

        canvas_path = mgr.generate_canvas_from_template("topic-center", {"TOPIC": "Test Topic"}, template_dir=self.templates_dir)

        assert canvas_path
        assert canvas_path.endswith(".canvas")
        full_path = os.path.join(self.vault_dir, canvas_path)
        assert os.path.exists(full_path)

        with open(full_path, "r", encoding="utf-8") as f:
            canvas = json.load(f)
        assert canvas["nodes"][0]["text"] == "# Test Topic"

    def test_generate_vault_index(self):
        notes = [
            {"id": "1", "title": "Fact One", "content": "Content", "subtype": "fact", "tags": ["phase-1"], "source": "system_observation", "confidence": 0.9, "created": "2026-01-01T00:00:00Z"},
            {"id": "2", "title": "Decision One", "content": "Content", "subtype": "decision", "tags": ["phase-2"], "source": "user_chat", "confidence": 0.6, "created": "2026-01-02T00:00:00Z"},
        ]
        self._write_memory_notes(notes)

        mgr = create_vault_manager(
            long_term_path=self.long_term_path,
            vault_path=self.vault_dir,
        )
        mgr.bridge.vault_path = self.vault_dir

        index_path = mgr.generate_vault_index()

        assert index_path == "INDEX.md"
        full_path = os.path.join(self.vault_dir, index_path)
        assert os.path.exists(full_path)

        content = open(full_path, "r", encoding="utf-8").read()
        assert "ARIA Memory Vault" in content
        assert "Total Notes" in content
        assert "fact" in content
        assert "decision" in content
        assert "phase-1" in content
        assert "phase-2" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])