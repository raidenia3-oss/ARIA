import subprocess, os, json, asyncio, re
import requests
from pathlib import Path

class ToolRegistry:
    """
    Registro de herramientas disponibles para el agente.
    Equivalente a las tools de Cline pero para Termux/Android.
    """

    def __init__(self, agent):
        self.agent = agent
        self.workspace = Path(agent.config.get("workspace",
                                                "/sdcard/AURA_workspace"))
        self.workspace.mkdir(parents=True, exist_ok=True)

    def list_capabilities(self) -> list:
        return [
            "run_command", "read_file", "write_file",
            "list_directory", "search_files", "web_search",
            "web_fetch", "aura_send", "aura_query",
            "godot_command", "install_package", "git_operation",
            "send_notification", "analyze_log",
        ]

    async def run(self, tool_name: str, args: dict) -> dict:
        tool_map = {
            "run_command":      self.run_command,
            "read_file":        self.read_file,
            "write_file":       self.write_file,
            "list_directory":   self.list_directory,
            "search_files":     self.search_files,
            "web_search":       self.web_search,
            "web_fetch":        self.web_fetch,
            "aura_send":        self.aura_send,
            "godot_command":    self.godot_command,
            "install_package":  self.install_package,
            "git_operation":    self.git_operation,
            "analyze_log":      self.analyze_log,
        }
        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Herramienta desconocida: {tool_name}"}
        try:
            if asyncio.iscoroutinefunction(tool):
                result = await tool(**args)
            else:
                result = tool(**args)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"error": str(e), "tool": tool_name}

    def run_command(self, command: str,
                    cwd: str = None, timeout: int = 30) -> dict:
        result = subprocess.run(
            command, shell=True,
            cwd=cwd or str(self.workspace),
            capture_output=True, text=True, timeout=timeout
        )
        return {
            "stdout": result.stdout, "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }

    def read_file(self, path: str,
                  lines: int = None, encoding: str = "utf-8") -> str:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"No existe: {path}")
        content = p.read_text(encoding=encoding, errors="replace")
        if lines:
            content = "\n".join(content.splitlines()[-lines:])
        return content

    def write_file(self, path: str, content: str,
                   mode: str = "w") -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        return f"Archivo guardado: {path} ({len(content)} chars)"

    def list_directory(self, path: str = None,
                       pattern: str = "*") -> list:
        p = Path(path or self.workspace)
        items = []
        for item in p.glob(pattern):
            items.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0
            })
        return sorted(items, key=lambda x: (x["type"], x["name"]))

    def search_files(self, query: str,
                     path: str = None, ext: str = None) -> list:
        search_path = Path(path or self.workspace)
        pattern = f"*.{ext}" if ext else "*"
        results = []
        for f in search_path.rglob(pattern):
            if f.is_file():
                try:
                    content = f.read_text(errors="replace")
                    if query.lower() in content.lower():
                        lines = [
                            (i+1, l.strip())
                            for i, l in enumerate(content.splitlines())
                            if query.lower() in l.lower()
                        ]
                        results.append({"file": str(f), "matches": lines[:5]})
                except Exception:
                    pass
        return results

    def install_package(self, package: str,
                        manager: str = "pip") -> dict:
        if manager == "pip":
            cmd = f"pip install {package} --break-system-packages -q"
        elif manager == "pkg":
            cmd = f"pkg install {package} -y"
        else:
            cmd = f"{manager} install {package}"
        return self.run_command(cmd)

    def git_operation(self, operation: str,
                      path: str = None, message: str = None) -> dict:
        cwd = path or str(self.workspace)
        ops = {
            "pull":   "git pull origin main",
            "status": "git status --short",
            "log":    "git log --oneline -10",
            "diff":   "git diff --stat",
            "push":   f'git add . && git commit -m "{message or "AME Agent update"}" && git push origin main'
        }
        cmd = ops.get(operation, f"git {operation}")
        return self.run_command(cmd, cwd=cwd)

    def web_search(self, query: str, num_results: int = 5) -> list:
        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": query, "format": "json", "no_html": 1}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            results = []
            for item in data.get("RelatedTopics", [])[:num_results]:
                if "Text" in item:
                    results.append({
                        "title": item.get("Text", "")[:100],
                        "url":   item.get("FirstURL", "")
                    })
            return results
        except Exception as e:
            return [{"error": str(e)}]

    def web_fetch(self, url: str,
                  extract_text: bool = True) -> str:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "AMEAgent/1.0"})
        if extract_text:
            text = re.sub(r'<[^>]+>', ' ', r.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:3000]
        return r.text[:5000]

    def analyze_log(self, log_path: str = None,
                    lines: int = 100) -> dict:
        path = log_path or str(self.agent.LOG_PATH)
        content = self.read_file(path, lines=lines)
        errors = [l for l in content.splitlines()
                  if "ERROR" in l or "FAIL" in l]
        warnings = [l for l in content.splitlines()
                    if "WARNING" in l or "WARN" in l]
        return {
            "total_lines": len(content.splitlines()),
            "errors": errors[-10:],
            "warnings": warnings[-10:],
            "summary": f"{len(errors)} errores, {len(warnings)} advertencias"
        }

    async def aura_send(self, event: str, payload: dict = {}) -> str:
        await self.agent._send(event, payload)
        return f"Evento enviado a AURA: {event}"

    async def godot_command(self, command: str,
                            args: dict = {}) -> dict:
        await self.agent._send("GODOT_REMOTE_CMD", {
            "command": command, "args": args, "source": "AME_AGENT"
        })
        return {"sent": True, "command": command}