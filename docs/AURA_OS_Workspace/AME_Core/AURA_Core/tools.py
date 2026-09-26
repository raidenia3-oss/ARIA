import os
import platform
import subprocess
import time
from typing import Optional
from urllib.parse import urlparse

import psutil
import requests
from bs4 import BeautifulSoup

# =============================================
# FILTRADO DE PRIVACIDAD (DNS Blocklist / Servo)
# =============================================
PRIVACY_BLOCKLIST: set[str] = {
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "googletagmanager.com",
    "googletagservices.com",
    "amazon-adsystem.com",
    "adsystem.amazon.com",
    "facebook.com/tr",
    "connect.facebook.net",
    "analytics.google.com",
    "google-analytics.com",
    "googleanalytics.com",
    "scorecardresearch.com",
    "quantserve.com",
    "outbrain.com",
    "taboola.com",
    "adservice.google.com",
    "tracking.mi.com",
    "telemetry.microsoft.com",
    "insights.hotjar.com",
    "cdn.segment.com",
    "segment.io",
    "mixpanel.com",
    "amplitude.com",
    "fullstory.com",
    "mouseflow.com",
}


def _is_blocked(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if ":" in host:
            host = host.split(":", 1)[0]
        return any(host == domain or host.endswith("." + domain) for domain in PRIVACY_BLOCKLIST)
    except Exception:
        return False


ALLOWED_COMMANDS = {
    "dir",
    "ls",
    "whoami",
    "date",
    "echo",
    "ping",
    "ipconfig",
    "ifconfig",
    "hostname",
    "ver",
    "type",
    "cat",
    "pwd",
    "df",
    "ps",
    "tasklist",
    "systeminfo",
}


def _safe_join(base: str, name: str) -> str:
    base = os.path.abspath(base)
    full = os.path.abspath(os.path.join(base, name))
    if not full.startswith(base):
        raise ValueError("Ruta fuera del directorio permitido.")
    return full


def list_files(path: str) -> str:
    try:
        entries = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            entries.append(f"{'[DIR] ' if os.path.isdir(full) else '[FILE]'} {name}")
        return "\n".join(entries) if entries else "Directorio vacío."
    except FileNotFoundError:
        return f"Error: No se encontró la ruta: {path}"
    except PermissionError:
        return f"Error: Sin permisos para leer: {path}"


def read_file(filename: str) -> str:
    base = r"C:\Users\User"
    try:
        path = _safe_join(base, filename)
        if os.path.isdir(path):
            return f"Error: '{filename}' es un directorio, no un archivo."
        if not os.path.exists(path):
            return f"Error: No existe '{filename}' en {base}."
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content if content else "El archivo está vacío."
    except ValueError:
        return f"Error: Ruta no permitida: '{filename}'."


def write_file(filename: str, content: str) -> str:
    base = r"C:\Users\User"
    try:
        path = _safe_join(base, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Archivo '{filename}' creado/actualizado correctamente."
    except ValueError:
        return f"Error: Ruta no permitida: '{filename}'."
    except OSError as e:
        return f"Error al escribir '{filename}': {e}"


def get_system_info() -> dict:
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "hostname": platform.node(),
        "cpu_cores": psutil.cpu_count(),
        "cpu_usage_percent": psutil.cpu_percent(interval=0.5),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "ram_usage_percent": psutil.virtual_memory().percent,
        "disk_usage_percent": (
            psutil.disk_usage("/").percent
            if platform.system() != "Windows"
            else psutil.disk_usage("C:\\").percent
        ),
    }


def execute_shell(command: str) -> dict:
    if platform.system() == "Windows":
        shell = True
        executable = None
    else:
        shell = False
        executable = "/bin/bash"
    try:
        result = subprocess.run(
            command,
            shell=shell,
            executable=executable,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


def web_fetch(url: str, max_chars: int = 4000) -> dict:
    """Scrapeo headless ligero con filtro anti-rastreadores."""
    if not url or not isinstance(url, str):
        return {"error": "URL inválida.", "blocked": False, "content": "", "title": ""}

    blocked = _is_blocked(url)
    if blocked:
        return {
            "error": "URL bloqueada por filtro de privacidad (dominio en blocklist).",
            "blocked": True,
            "content": "",
            "title": "",
        }

    try:
        resp = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "AURA-Core/1.0 (+https://github.com/raidenia3-oss/AURA-server.01)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "close",
            },
        )
        text = resp.text or ""
        title = ""
        try:
            soup = BeautifulSoup(text, "html.parser")
            title = (soup.title.string or "").strip() if soup.title else ""
            visible = " ".join(
                chunk.strip() for chunk in soup.get_text("\n").splitlines() if chunk.strip()
            )
            text = visible
        except Exception:
            pass
        truncated = text[:max_chars]
        return {
            "error": None,
            "blocked": False,
            "title": title,
            "content": truncated,
            "chars": len(truncated),
            "status": resp.status_code,
        }
    except requests.exceptions.Timeout:
        return {
            "error": "Timeout al acceder a la URL.",
            "blocked": False,
            "content": "",
            "title": "",
        }
    except requests.exceptions.ConnectionError:
        return {
            "error": "Error de conexión con el dominio.",
            "blocked": False,
            "content": "",
            "title": "",
        }
    except Exception as e:
        return {"error": f"Error inesperado: {e}", "blocked": False, "content": "", "title": ""}


def scan_project_context(root: Optional[str] = None, max_files: int = 80) -> dict:
    """Escaneo ligero del proyecto para inyectar contexto RAG."""
    base = os.path.abspath(root or os.getcwd())
    ignore_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".idea",
        ".vscode",
        "AURA_Core/logs",
    }
    summary = {
        "root": base,
        "files": 0,
        "dirs": 0,
        "extensions": {},
        "key_files": [],
        "sample": [],
        "errors": [],
    }
    try:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            summary["dirs"] += len(dirnames)
            for fn in filenames:
                if summary["files"] >= max_files:
                    break
                full = os.path.join(dirpath, fn)
                try:
                    rel = os.path.relpath(full, base)
                    ext = os.path.splitext(fn)[1].lower()
                    summary["extensions"][ext] = summary["extensions"].get(ext, 0) + 1
                    summary["files"] += 1
                    if any(
                        k in fn.lower()
                        for k in [
                            "readme",
                            "requirements",
                            "package.json",
                            "pyproject",
                            "docker-compose",
                            "makefile",
                            "manifest",
                            "build.gradle",
                            "settings.gradle",
                            "gradle.properties",
                        ]
                    ):
                        summary["key_files"].append(rel)
                    if summary["files"] <= 12:
                        try:
                            with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                                raw = fh.read(280)
                            summary["sample"].append(
                                {"path": rel, "preview": raw.replace("\n", " ")[:200]}
                            )
                        except Exception as e:
                            summary["errors"].append({"path": rel, "error": str(e)})
                except Exception:
                    pass
            if summary["files"] >= max_files:
                break
    except Exception as e:
        summary["errors"].append({"root": base, "error": str(e)})
    return summary


# =============================================
# AGENTE DEBATE ANALYST (FASE 4 / FASE 6)
# =============================================


def _generate_via_provider(prompt: str, persona: str = "analyst") -> dict:
    """Genera respuesta usando el proveedor disponible."""
    try:
        import requests  # type: ignore[import-untyped]

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return {
                "error": "OPENROUTER_API_KEY no configurada",
                "response": "Servicio no disponible.",
            }
        system_map = {
            "optimist": "Eres un agente optimista. Encuentra ventajas, oportunidades y beneficios.",
            "critic": "Eres un agente escéptico. Identifica riesgos, fallos y problemas potenciales.",
            "analyst": "Eres un analista objetivo. Expone datos, contexto y estructura claramente.",
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "mistralai/mistral-small-3.1-24b-instruct:free",
                "messages": [
                    {"role": "system", "content": system_map.get(persona, system_map["analyst"])},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.7,
            },
            timeout=60,
        )
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "ok": True,
            "text": text or "Sin respuesta del modelo.",
            "provider": "openrouter",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "text": f"Error: {e}"}


def run_agent_debate(topic: str) -> dict:
    """Orquesta un debate entre 3 sub-agentes virtuales."""
    if not topic or not topic.strip():
        return {"error": "El tema no puede estar vacío."}

    transcript: list[dict] = []
    start = time.time()

    # 1. Analista introduce el tema
    analyst_intro = (
        f"Vamos a analizar el siguiente tema desde múltiples perspectivas:\n\n"
        f"TEMA: {topic.strip()}\n\n"
        f"Por favor, presenta un resumen objetivo del tema en 3-4 puntos clave."
    )
    analyst_resp = _generate_via_provider(analyst_intro, persona="analyst")
    transcript.append(
        {
            "agent": "Agente Analista",
            "icon": "📊",
            "prompt": analyst_intro,
            "response": analyst_resp.get("text", ""),
            "provider": analyst_resp.get("provider"),
        }
    )

    # 2. Optimista responde
    optimistic_prompt = (
        f"Basado en este análisis inicial:\n\n{transcript[-1]['response']}\n\n"
        f"Responde como el AGENTE OPTIMISTA y lista las ventajas, oportunidades y beneficios de: {topic.strip()}"
    )
    opt_resp = _generate_via_provider(optimistic_prompt, persona="optimist")
    transcript.append(
        {
            "agent": "Agente Optimista",
            "icon": "🟢",
            "prompt": optimistic_prompt,
            "response": opt_resp.get("text", ""),
            "provider": opt_resp.get("provider"),
        }
    )

    # 3. Crítico responde
    critic_prompt = (
        f"Considerando el análisis y la postura optimista:\n\n"
        f"ANÁLISIS: {transcript[0]['response']}\n\n"
        f"OPTIMISTA: {transcript[-1]['response']}\n\n"
        f"Responde como el AGENTE CRÍTICO/ESCÉPTICO y lista riesgos, fallos y contras de: {topic.strip()}"
    )
    crit_resp = _generate_via_provider(critic_prompt, persona="critic")
    transcript.append(
        {
            "agent": "Agente Crítico",
            "icon": "🔴",
            "prompt": critic_prompt,
            "response": crit_resp.get("text", ""),
            "provider": crit_resp.get("provider"),
        }
    )

    # 4. Consolidación final
    transcript_lines = []
    for tx in transcript:
        transcript_lines.append(f"[{tx['agent']}]: {tx['response']}")
    transcript_text = chr(10).join(transcript_lines)
    consolidation_prompt = (
        "Based on the following debate transcript, produce a concise report with:\n"
        "1) Resumen del tema\n2) Pros (optimista)\n3) Contras (crítico)\n4) Veredicto final ponderado\n\n"
        f"TRANSCRIPT:\n{transcript_text}"
    )
    final_resp = _generate_via_provider(consolidation_prompt, persona="analyst")
    transcript.append(
        {
            "agent": "Reporte Consolidado",
            "icon": "📝",
            "prompt": consolidation_prompt,
            "response": final_resp.get("text", ""),
            "provider": final_resp.get("provider"),
            "is_final": True,
        }
    )

    return {
        "ok": True,
        "topic": topic.strip(),
        "duration_seconds": round(time.time() - start, 2),
        "agents": len(transcript),
        "transcript": transcript,
        "final_report": final_resp.get("text", ""),
    }
