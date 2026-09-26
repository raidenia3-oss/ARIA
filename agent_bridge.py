#!/usr/bin/env python3
"""
AURA Agent Bridge — Integration with code agents like Kilo and Cline
Provides a unified interface to send prompts, execute tasks, and receive
results from autonomous coding agents.
"""

from __future__ import annotations

import json
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent


class AgentTask:
    def __init__(self, task_id: str, agent: str, prompt: str, status: str = "pending") -> None:
        self.task_id = task_id
        self.agent = agent
        self.prompt = prompt
        self.status = status
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.created_at = __import__("time").time()


class AgentBridge:
    def __init__(self, project_root: Path = ROOT) -> None:
        self.project_root = project_root
        self.agents: Dict[str, Dict[str, Any]] = {
            "kilo": {"available": False, "cmd": "kilo", "description": "Kilo coding agent"},
            "cline": {"available": False, "cmd": "cline", "description": "Cline coding agent"},
        }
        self._detect_agents()
        self.task_queue: queue.Queue = queue.Queue()
        self.tasks: Dict[str, AgentTask] = {}
        self._task_counter = 0
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

    def _detect_agents(self) -> None:
        for name, info in self.agents.items():
            if shutil.which(info["cmd"]):
                info["available"] = True
            else:
                alt_paths = []
                if name == "kilo":
                    alt_paths = [
                        Path.home() / ".kilo" / "bin" / "kilo",
                        Path.home() / ".local" / "bin" / "kilo",
                        Path("/usr/local/bin/kilo"),
                        Path("/usr/bin/kilo"),
                    ]
                elif name == "cline":
                    alt_paths = [
                        Path.home() / ".vscode" / "extensions" / "saoudrizwan.claude-dev" / "cli" / "cline",
                    ]
                for p in alt_paths:
                    if p.exists():
                        info["available"] = True
                        info["cmd"] = str(p)
                        break

    def get_available_agents(self) -> List[str]:
        return [name for name, info in self.agents.items() if info["available"]]

    def is_available(self, agent: str) -> bool:
        return self.agents.get(agent, {}).get("available", False)

    def create_task(self, agent: str, prompt: str) -> AgentTask:
        self._task_counter += 1
        task_id = f"task_{self._task_counter:04d}"
        task = AgentTask(task_id=task_id, agent=agent, prompt=prompt)
        self.tasks[task_id] = task
        self.task_queue.put(task)
        return task

    def start_worker(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def stop_worker(self) -> None:
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

    def _worker(self) -> None:
        while self._running:
            try:
                task = self.task_queue.get(timeout=0.5)
                self._execute_task(task)
            except queue.Empty:
                continue
            except Exception as exc:
                pass

    def _execute_task(self, task: AgentTask) -> None:
        task.status = "running"
        agent_info = self.agents.get(task.agent)
        if not agent_info or not agent_info["available"]:
            task.status = "failed"
            task.error = f"Agent '{task.agent}' not available"
            return

        try:
            cmd = agent_info["cmd"]
            if task.agent == "kilo":
                result = self._run_kilo(task.prompt)
            elif task.agent == "cline":
                result = self._run_cline(task.prompt)
            else:
                result = self._run_generic(cmd, task.prompt)

            task.result = result
            task.status = "completed"
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)

    def _run_kilo(self, prompt: str) -> str:
        cmd = [
            self.agents["kilo"]["cmd"],
            "--quiet",
            "--cwd", str(self.project_root),
            "--prompt", prompt,
        ]
        print(f"DEBUG: Executing Kilo with command: {cmd}") # Added for debugging
        env = os.environ.copy()
        env["KILO_NO_UPDATE"] = "1"
        proc = subprocess.run(
            cmd,
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "Kilo failed")
        return proc.stdout.strip()

    def _run_cline(self, prompt: str) -> str:
        cmd = [
            self.agents["cline"]["cmd"],
            "--cwd", str(self.project_root),
            "--prompt", prompt,
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "Cline failed")
        return proc.stdout.strip()

    def _run_generic(self, cmd: str, prompt: str) -> str:
        proc = subprocess.run(
            [cmd, prompt],
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            timeout=300,
            shell=platform.system() == "Windows",
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "Command failed")
        return proc.stdout.strip()

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[AgentTask]:
        return list(self.tasks.values())


# ---------------------------------------------------------------------------
# Diagnostic / auto-fix helpers
# ---------------------------------------------------------------------------
class AutoFixer:
    def __init__(self, project_root: Path = ROOT) -> None:
        self.project_root = project_root
        self.issues: List[Dict[str, Any]] = []
        self.fixes_applied: List[str] = []

    def scan(self) -> List[Dict[str, Any]]:
        self.issues = []
        self._check_python_syntax()
        self._check_node_modules()
        self._check_ruby_deps()
        self._check_env_files()
        self._check_vscode_config()
        self._check_imports()
        self._check_docker()
        return self.issues

    def _check_python_syntax(self) -> None:
        for py_file in self.project_root.rglob("*.py"):
            if any(part in str(py_file) for part in ["node_modules", ".git", "__pycache__", ".venv"]):
                continue
            try:
                code = py_file.read_text(encoding="utf-8", errors="ignore")
                compile(code, str(py_file), "exec")
            except SyntaxError as exc:
                self.issues.append({
                    "type": "python_syntax",
                    "file": str(py_file.relative_to(self.project_root)),
                    "line": exc.lineno,
                    "message": exc.msg,
                    "severity": "error",
                    "fixable": False,
                })

    def _check_node_modules(self) -> None:
        frontend = self.project_root / "frontend"
        if not frontend.exists():
            return
        node_modules = frontend / "node_modules"
        if not node_modules.exists():
            self.issues.append({
                "type": "missing_node_modules",
                "file": "frontend/",
                "message": "node_modules missing — run npm install",
                "severity": "error",
                "fixable": True,
            })

    def _check_ruby_deps(self) -> None:
        for svc in ["discord-bot", "dsl-compiler"]:
            svc_path = self.project_root / "services" / svc
            gemfile = svc_path / "Gemfile"
            if gemfile.exists() and not (svc_path / "Gemfile.lock").exists():
                self.issues.append({
                    "type": "missing_ruby_deps",
                    "file": f"services/{svc}/",
                    "message": "Gemfile.lock missing — run bundle install",
                    "severity": "warning",
                    "fixable": True,
                })

    def _check_env_files(self) -> None:
        root_env = self.project_root / ".env"
        if not root_env.exists() and (self.project_root / ".env.example").exists():
            self.issues.append({
                "type": "missing_env",
                "file": ".env",
                "message": ".env missing — copy from .env.example",
                "severity": "warning",
                "fixable": True,
            })

    def _check_vscode_config(self) -> None:
        vscode_dir = self.project_root / ".vscode"
        for fname in ["extensions.json", "settings.json", "launch.json", "tasks.json"]:
            if not (vscode_dir / fname).exists():
                self.issues.append({
                    "type": "missing_vscode_config",
                    "file": f".vscode/{fname}",
                    "message": f"{fname} missing in .vscode/",
                    "severity": "warning",
                    "fixable": True,
                })

    def _check_imports(self) -> None:
        imports_map = {
            "backend/main.py": ["backend.database", "backend.models", "ame_backend"],
            "services/discord-bot/bot.rb": ["discordrb", "httparty", "redis"],
        }
        for rel_path, expected_imports in imports_map.items():
            target = self.project_root / rel_path
            if not target.exists():
                continue
            content = target.read_text(encoding="utf-8", errors="ignore")
            for imp in expected_imports:
                if imp not in content:
                    self.issues.append({
                        "type": "missing_import",
                        "file": rel_path,
                        "message": f"Missing import: {imp}",
                        "severity": "warning",
                        "fixable": True,
                    })

    def _check_docker(self) -> None:
        compose = self.project_root / "docker-compose.yml"
        if not compose.exists():
            self.issues.append({
                "type": "missing_docker_compose",
                "file": "docker-compose.yml",
                "message": "docker-compose.yml missing",
                "severity": "warning",
                "fixable": False,
            })

    def auto_fix(self) -> List[str]:
        self.fixes_applied = []
        for issue in self.issues:
            if not issue.get("fixable", False):
                continue
            try:
                if issue["type"] == "missing_node_modules":
                    frontend = self.project_root / "frontend"
                    subprocess.run(["npm", "install"], cwd=str(frontend), capture_output=True, timeout=120)
                    self.fixes_applied.append(f"Installed npm dependencies in frontend/")
                elif issue["type"] == "missing_ruby_deps":
                    for svc in ["discord-bot", "dsl-compiler"]:
                        svc_path = self.project_root / "services" / svc
                        if (svc_path / "Gemfile").exists():
                            subprocess.run(["bundle", "install"], cwd=str(svc_path), capture_output=True, timeout=120)
                            self.fixes_applied.append(f"Installed Ruby deps for {svc}")
                elif issue["type"] == "missing_env":
                    example = self.project_root / ".env.example"
                    if example.exists():
                        shutil.copy(example, self.project_root / ".env")
                        self.fixes_applied.append("Created .env from .env.example")
                elif issue["type"] == "missing_vscode_config":
                    vscode_dir = self.project_root / ".vscode"
                    vscode_dir.mkdir(exist_ok=True)
                    fname = issue["file"].split("/")[-1]
                    if fname == "extensions.json":
                        (vscode_dir / "extensions.json").write_text('{"recommendations":[],"unwantedRecommendations":[]}')
                    elif fname == "settings.json":
                        (vscode_dir / "settings.json").write_text('{"python.pythonPath":"python"}')
                    elif fname == "launch.json":
                        (vscode_dir / "launch.json").write_text('{"version":"0.2.0","configurations":[]}')
                    elif fname == "tasks.json":
                        (vscode_dir / "tasks.json").write_text('{"version":"2.0.0","tasks":[]}')
                    self.fixes_applied.append(f"Created {fname}")
            except Exception as exc:
                self.fixes_applied.append(f"FAILED to fix {issue['type']}: {exc}")
        return self.fixes_applied
