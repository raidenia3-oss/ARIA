# -*- coding: utf-8 -*-
"""AURA OS — AutoDocumentation Engine.

Generates docs, README, changelog, API docs, and architectural guides
from code analysis and runtime metadata.
"""
from __future__ import annotations

import ast
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.AutoDoc")


class DocSection:
    def __init__(self, title: str, content: str, level: int = 1) -> None:
        self.title = title
        self.content = content
        self.level = level


class AutoDocumenter:
    """Automatically generates documentation from Python code."""

    def __init__(self, project_root: str = ".", output_dir: str = "docs") -> None:
        self.project_root = Path(project_root).resolve()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = {}
        self._last_update: float = 0.0

    def scan_project(self) -> Dict[str, Any]:
        modules: List[Dict[str, Any]] = []
        for py_file in self._find_py_files():
            try:
                info = self._analyze_file(py_file)
                if info:
                    modules.append(info)
            except Exception as exc:
                logger.debug("Skip %s: %s", py_file, exc)
        result = {
            "timestamp": datetime.now().isoformat(),
            "root": str(self.project_root),
            "total_modules": len(modules),
            "modules": modules,
        }
        self._cache["project_scan"] = result
        self._last_update = time.time()
        return result

    def _find_py_files(self) -> List[Path]:
        skip = {".git", "__pycache__", ".venv", "node_modules", ".vscode",
                "data", "dist", "build", "archives", "aura-os", "AURA_Core",
                "godot", "docs", "AURA_APP", ".disabled", ".github",
                "archive", "node_modules", "dist", "build"}
        results = []
        for dirpath, dirnames, filenames in os.walk(self.project_root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for f in filenames:
                if f.endswith(".py"):
                    results.append(Path(dirpath) / f)
        return results[:500]

    def _analyze_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return None

        relative = filepath.relative_to(self.project_root)
        functions = []
        classes = []
        imports = []
        docstring = ast.get_docstring(tree) or ""

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node) or "",
                })
            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append({
                            "name": item.name,
                            "args": [a.arg for a in item.args.args],
                            "docstring": ast.get_docstring(item) or "",
                        })
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node) or "",
                })
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imports.append(alias.name)

        return {
            "path": str(relative),
            "module": filepath.stem,
            "docstring": docstring,
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "lines": len(source.splitlines()),
            "size_kb": round(len(source.encode("utf-8")) / 1024, 1),
        }

    def generate_readme(self, project_name: str = "AURA OS") -> str:
        scan = self.scan_project()
        lines: List[str] = [f"# {project_name}", "", "## Estructura del Proyecto", ""]
        for mod in scan.get("modules", []):
            lines.append(f"- `{mod['path']}` — {mod['docstring'][:80] if mod['docstring'] else mod['module']}")
        lines.append("")
        lines.append("## Módulos Principales")
        lines.append("")
        for mod in scan.get("modules", []):
            if mod["classes"]:
                for cls in mod["classes"]:
                    lines.append(f"- **{cls['name']}** ({mod['path']})")
        lines.append("")
        return "\n".join(lines)

    def generate_changelog(self, version: str = "2.1.0") -> str:
        now = datetime.now()
        lines = [f"# Changelog v{version}", "", f"## {now.strftime('%Y-%m-%d')}", ""]
        if "project_scan" in self._cache:
            scan = self._cache["project_scan"]
            new_modules = [m for m in scan.get("modules", []) if m["lines"] > 100]
            if new_modules:
                lines.append("### Nuevos módulos")
                for m in new_modules:
                    lines.append(f"- `{m['path']}` ({m['lines']} líneas)")
                lines.append("")
        return "\n".join(lines)

    def generate_api_docs(self) -> str:
        scan = self.scan_project()
        lines: List[str] = ["# API Documentation", "", "## Endpoints Disponibles", ""]
        for mod in scan.get("modules", []):
            if "route" in mod["module"] or "api" in mod["module"]:
                lines.append(f"### {mod['path']}")
                for func in mod.get("functions", []):
                    args = ", ".join(func["args"])
                    lines.append(f"- `{func['name']}({args})` — {func['docstring'][:100]}")
                lines.append("")
        return "\n".join(lines)

    def generate_architecture_guide(self) -> str:
        scan = self.scan_project()
        sections: List[DocSection] = []
        sections.append(DocSection("Arquitectura de AURA OS", "Sistema modular con backend FastAPI, frontend HUD, y daemon autónomo.", 1))
        core_mods = [m for m in scan.get("modules", []) if "/core/" in m["path"]]
        if core_mods:
            sections.append(DocSection("Núcleo", f"{len(core_mods)} módulos de core.", 2))
        daemon_mods = [m for m in scan.get("modules", []) if "/daemon/" in m["path"]]
        if daemon_mods:
            sections.append(DocSection("Daemon", f"{len(daemon_mods)} módulos de daemon.", 2))
        api_mods = [m for m in scan.get("modules", []) if "/api/" in m["path"]]
        if api_mods:
            sections.append(DocSection("API Routes", f"{len(api_mods)} módulos de API.", 2))
        agent_mods = [m for m in scan.get("modules", []) if "/agents/" in m["path"]]
        if agent_mods:
            sections.append(DocSection("Agentes", f"{len(agent_mods)} módulos de agentes.", 2))
        auto_mods = [m for m in scan.get("modules", []) if "/automation/" in m["path"]]
        if auto_mods:
            sections.append(DocSection("Automatización", f"{len(auto_mods)} módulos.", 2))
        learning_mods = [m for m in scan.get("modules", []) if "/learning/" in m["path"]]
        if learning_mods:
            sections.append(DocSection("Aprendizaje", f"{len(learning_mods)} módulos de aprendizaje.", 2))
        out: List[str] = ["# Guía de Arquitectura", ""]
        for s in sections:
            out.append("#" * s.level + f" {s.title}")
            out.append(s.content)
            out.append("")
        return "\n".join(out)

    def get_documentation_status(self) -> Dict[str, Any]:
        return {
            "last_update": datetime.fromtimestamp(self._last_update).isoformat() if self._last_update else None,
            "project_scanned": "project_scan" in self._cache,
            "total_modules": len(self._cache.get("project_scan", {}).get("modules", [])),
            "generated_files": list(self.output_dir.rglob("*")) if self.output_dir.exists() else [],
        }


auto_documenter = AutoDocumenter()
