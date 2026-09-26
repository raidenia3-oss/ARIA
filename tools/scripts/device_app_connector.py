#!/usr/bin/env python3
"""
AURA Device App Connector — Entorno de conexión con apps del dispositivo.

Detecta apps instaladas, procesos activos y ventanas en el sistema,
generando pares Q/A para entrenar al modelo en automatización y flujos
de trabajo con aplicaciones reales del dispositivo.

Funcionalidades:
  - Listado de procesos activos (nombre, PID, memoria, CPU)
  - Detección de ventanas activas (título, proceso)
  - Identificación de apps instaladas (Windows Registry)
  - Generación de comandos útiles por app (PowerShell, CLI)
  - Generación de flujos de automatización multi-app

Uso:
  python scripts/device_app_connector.py --count 50 --output training-data-device.jsonl
  python scripts/device_app_connector.py --snapshot --format json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import random
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DeviceAppConnector")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-device.jsonl"

APP_CATALOG: Dict[str, List[str]] = {
    "browser": ["Chrome", "Firefox", "Edge", "Safari", "Brave", "Vivaldi"],
    "ide": ["VS Code", "PyCharm", "IntelliJ", "Sublime Text", "Notepad++", "Vim"],
    "communication": ["Discord", "Slack", "Teams", "Zoom", "WhatsApp", "Telegram", "Skype"],
    "media": ["Spotify", "VLC", "OBS Studio", "Audacity", "Photoshop", "GIMP"],
    "productivity": ["Notion", "Obsidian", "Excel", "Word", "PowerPoint", "Todoist", "OneNote"],
    "devops": ["Docker Desktop", "Postman", "GitKraken", "Terraform", "Kubernetes Dashboard", "WSL"],
    "system": ["Task Manager", "Command Prompt", "PowerShell", "Windows Terminal", "File Explorer", "Registry Editor"],
    "ai": ["Ollama", "LM Studio", "Jan.ai", "ChatGPT Desktop", "Claude Desktop", "Continue.dev"],
}

DEVICE_TEMPLATES: List[Dict] = [
    {
        "template": (
            "El proceso {proc} está consumiendo {mem} MB de memoria. "
            "¿Es normal? Si no, ¿qué comandos usarías para investigarlo y detenerlo?"
        ),
        "variables": {
            "proc": ["chrome.exe", "Code.exe", "docker.exe", "ollama.exe", "python.exe", "node.exe", "svchost.exe"],
            "mem": [500, 1200, 2000, 3500, 800, 1500, 400],
        },
        "difficulty": "easy",
        "answer": (
            "Evaluación:\n"
            "- {proc} típicamente usa entre 200MB y 1500MB según actividad.\n"
            "- {mem} MB está dentro del rango esperado para cargas moderadas; si supera 2GB, revisar plugins o pestañas.\n\n"
            "Comandos de investigación:\n"
            "  tasklist | findstr {proc}\n"
            "  Get-Process {proc} | Sort CPU -Descending\n"
            "  Get-Counter '\\Process({proc})\\Working Set - Private'\n\n"
            "Si es anormal:\n"
            "  Stop-Process -Name {proc} -Force (solo si no hay trabajo sin guardar)"
        ),
    },
    {
        "template": (
            "Necesito automatizar el siguiente flujo: abrir {app1}, "
            "copiar datos de {app2}, pegarlos en {app1} y guardar. "
            "¿Qué herramientas y pasos usarías en Windows?"
        ),
        "variables": {
            "app1": ["Excel", "Word", "Notion", "VS Code", "PowerShell", "Notepad"],
            "app2": ["Chrome", "Firefox", "Discord", "Slack", "Outlook", "Teams"],
        },
        "difficulty": "medium",
        "answer": (
            "Herramientas recomendadas para flujo {app1} → {app2}:\n"
            "1. AutoHotkey (v2): scripting rápido de UI.\n"
            "2. Python + pyautogui/pywinauto: mayor control y logging.\n"
            "3. PowerShell + UIAutomation: nativo, sin dependencias.\n\n"
            "Pasos:\n"
            "1. Mapear controles (ahk, Inspect.exe o UIA Verify).\n"
            "2. Definir trigger (hotkey, schedule, clipboard monitor).\n"
            "3. Implementar copy-paste con validación de formato.\n"
            "4. Agregar manejo de errores y logs.\n"
            "5. Probar en múltiples resoluciones."
        ),
    },
    {
        "template": (
            "Tengo {n} archivos PDF en una carpeta y necesito extraer texto "
            "y metadata (autor, título, páginas) para indexarlos. "
            "Diseña una solución automatizada para Windows."
        ),
        "variables": {
            "n": [50, 200, 1000],
        },
        "difficulty": "medium",
        "answer": (
            "Solución automatizada para {n} PDFs:\n"
            "1. Librería: PyMuPDF (fitz) o pdfplumber para extracción precisa.\n"
            "2. Script:\n"
            "   import fitz\n"
            "   for pdf in Path('carpeta').rglob('*.pdf'):\n"
            "       doc = fitz.open(pdf)\n"
            "       meta = doc.metadata\n"
            "       text = ''.join(page.get_text() for page in doc)\n"
            "       # guardar en JSONL/SQLite\n"
            "3. Indexación: Meilisearch o Elasticsearch para búsqueda full-text.\n"
            "4. Scheduling: Task Scheduler o Windows Service para ejecución periódica."
        ),
    },
    {
        "template": (
            "El equipo usa {app} para colaborar, pero necesita un bot que "
            "monitoree el canal {channel} y responda automáticamente cuando "
            "se mencionen keywords como {keywords}. Diseña la arquitectura."
        ),
        "variables": {
            "app": ["Slack", "Discord", "Teams"],
            "channel": ["#devops", "#general", "#incidentes", "#proyecto-alpha"],
            "keywords": ["'deploy failed'", "'Kubernetes'", "'alerta'", "'review needed'"],
        },
        "difficulty": "hard",
        "answer": (
            "Arquitectura del bot para {app} en {channel}:\n"
            "1. SDK oficial de {app} para recepción de eventos.\n"
            "2. Webhook listener o socket según disponibilidad.\n"
            "3. Motor de matching:\n"
            "   - Keywords exactas y regex.\n"
            "   - Fuse de scoring si hay múltiples coincidencias.\n"
            "4. Motor de respuesta:\n"
            "   - Templates predefinidos.\n"
            "   - Fallback a LLM local vía Ollama.\n"
            "5. Cola de mensajes para desacoplar recepción de respuesta.\n"
            "6. Circuit breaker y backoff ante rate limits.\n"
            "7. Logging estructurado + métricas de precisión."
        ),
    },
    {
        "template": (
            "Necesito monitorear el uso de CPU y RAM de las apps principales "
            "y recibir alertas cuando algo supere {cpu}% CPU o {ram}% RAM. "
            "Propón una solución con scripts nativos de Windows."
        ),
        "variables": {
            "cpu": [80, 90, 95],
            "ram": [85, 90, 95],
        },
        "difficulty": "medium",
        "answer": (
            "Solución de monitoreo nativo Windows:\n"
            "1. Performance Counters:\n"
            "   Get-Counter '\\Process(*)\\% Processor Time' -SampleInterval 5 -MaxSamples 1\n"
            "2. Script PowerShell:\n"
            "   $cpu_threshold = {cpu}\n"
            "   $ram_threshold = {ram}\n"
            "   foreach ($proc in Get-Process) {{\n"
            "       if ($proc.CPU -gt $cpu_threshold -or $proc.WorkingSet64/1MB -gt $ram_threshold) {{\n"
            "           # alertar (log, toast, email)\n"
            "       }}\n"
            "   }}\n"
            "3. Programar con Task Scheduler cada 5 minutos.\n"
            "4. Ventilación: no alertar más de 1 vez cada N minutos para el mismo proceso."
        ),
    },
    {
        "template": (
            "Quiero crear un acceso directo en Windows que ejecute un script Python "
            "con permisos elevados sin abrir una consola visible. "
            "¿Cómo lo hago? Menciona VBS, schtasks y políticas de ejecución."
        ),
        "variables": {},
        "difficulty": "medium",
        "answer": (
            "Tres métodos para ejecutar Python elevado sin consola:\n\n"
            "Opción 1 — VBS (más simple):\n"
            "   Set sh = CreateObject(\"Wscript.Shell\")\n"
            "   sh.Run \"cmd /c python C:\\ruta\\script.py\", 0, False\n\n"
            "Opción 2 — Task Scheduler (más robusto):\n"
            "   schtasks /create /tn \"AURAScript\" /tr \"python C:\\ruta\\script.py\" /sc ONLOGON /rl HIGHEST /f\n\n"
            "Opción 3 — Acceso directo:\n"
            "   Destino: powershell -WindowStyle Hidden -Command \"python C:\\ruta\\script.py\"\n\n"
            "Consideraciones:\n"
            "- Set-ExecutionPolicy RemoteSigned para scripts locales.\n"
            "- Firmar script con código si es crítica la seguridad.\n"
            "- No hardcodear credenciales; usar variables de entorno o Windows Credential Manager."
        ),
    },
    {
        "template": (
            "Tengo instaladas las apps: {apps}. "
            "Propón 5 flujos de automatización útiles que conecten al menos 2 de estas apps."
        ),
        "variables": {
            "apps": [
                "VS Code, Docker, GitHub, Slack",
                "Chrome, Excel, Outlook, Teams",
                "OBS, Discord, Spotify, Telegram",
                "Python, PostgreSQL, Redis, Grafana",
            ],
        },
        "difficulty": "hard",
        "answer": (
            "Flujos de automatización con {apps}:\n\n"
            "1. VS Code → Docker → GitHub → Slack:\n"
            "   Git push → CI/CD en GitHub Actions → build Docker → deploy → notificación Slack.\n\n"
            "2. Chrome → Excel → Outlook:\n"
            "   Scraping de tabla web → Excel macro → adjuntar CSV en Outlook.\n\n"
            "3. OBS → Discord → Spotify:\n"
            "   Inicio de stream OBS → mensaje Discord → playlist Spotify temática.\n\n"
            "4. Python → PostgreSQL → Redis → Grafana:\n"
            "   ETL Python → cache Redis → dashboard Grafana con alertas.\n\n"
            "Cada flujo define: trigger, transformación, acción y manejo de errores."
        ),
    },
    {
        "template": (
            "¿Cómo ejecutar un comando PowerShell que requiera permisos de administrador "
            "desde un script Python en Windows? Menciona runas, manifest y UAC."
        ),
        "variables": {},
        "difficulty": "medium",
        "answer": (
            "Métodos para elevar privilegios desde Python:\n\n"
            "1. runas:\n"
            "   subprocess.run(['runas', '/user:Administrator', 'powershell', '-Command', '...'])\n\n"
            "2. ShellExecute con 'runas' (pywin32):\n"
            "   import win32api\n"
            "   win32api.ShellExecute(0, 'runas', 'powershell.exe', '-Command ...', None, 1)\n\n"
            "3. Manifest en acceso directo:\n"
            "   Agregar requestedExecutionLevel level='requireAdministrator' en el .manifest.\n\n"
            "Consideraciones:\n"
            "- UAC prompt es inevitable para administrador.\n"
            "- Mínimo privilegio: usar solo lo necesario, no administrador por defecto.\n"
            "- Logging obligatorio de acciones elevadas para auditoría."
        ),
    },
    {
        "template": (
            "Un desarrollador tiene {app1} y {app2} abiertos. "
            "¿Cómo detectar qué ventana está activa y enviar un comando "
            "de teclado solo a esa app sin afectar las demás?"
        ),
        "variables": {
            "app1": ["VS Code", "Chrome", "Word", "Excel"],
            "app2": ["Discord", "Slack", "Teams", "Outlook"],
        },
        "difficulty": "hard",
        "answer": (
            "Detección y envío selectivo:\n"
            "1. Detectar ventana activa:\n"
            "   - PowerShell: (Get-Process | Where-Object {$_.MainWindowTitle -ne ''}).MainWindowHandle\n"
            "   - pygetwindow: gw.getActiveWindow()\n"
            "2. Verificar proceso asociado al HWND.\n"
            "3. Enviar input solo a esa ventana:\n"
            "   - AttachThreadInput para adjuntar input a ese hilo.\n"
            "   - SendMessage/PostMessage con WM_KEYDOWN.\n"
            "   - O pyautogui.click(x, y) con coordenadas relativas a la ventana.\n\n"
            "Precauciones:\n"
            "- Verificar que la ventana esté en foreground antes de enviar.\n"
            "- Pequeño delay entre teclas para simular humano.\n"
            "- Manejar ventanas minimizadas o en segundo plano."
        ),
    },
]


class DeviceAppConnector:
    """Detecta apps del dispositivo y genera datos de entrenamiento."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()
        self.snapshot: Optional[Dict[str, Any]] = None

    def _key(self, idx: int, difficulty: str) -> str:
        return f"device:{idx}:{difficulty}"

    def _fill_template(self, template: str, variables: Dict) -> str:
        result = template
        for var, values in variables.items():
            if isinstance(values, list):
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                result = result.replace("{" + var + "}", val)
        remaining = re.findall(r"\{([A-Z0-9_]+)\}", result)
        for var in remaining:
            result = result.replace("{" + var + "}", f"[{var}]")
        return result

    def get_active_processes(self) -> List[Dict[str, Any]]:
        """Obtiene lista de procesos activos del sistema."""
        processes = []
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
                try:
                    info = proc.info
                    processes.append({
                        "pid": info["pid"],
                        "name": info["name"],
                        "memory_mb": round(info["memory_info"].rss / (1024 * 1024), 1),
                        "cpu_percent": info["cpu_percent"],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logger.warning("psutil not installed; process detection skipped")
        return processes

    def get_active_windows(self) -> List[Dict[str, str]]:
        """Obtiene ventanas activas (solo Windows)."""
        if platform.system() != "Windows":
            return []
        windows = []
        try:
            import pygetwindow as gw
            for win in gw.getAllWindows():
                if win.title:
                    windows.append({
                        "title": win.title,
                        "process": win.title,
                        "left": win.left,
                        "top": win.top,
                        "width": win.width,
                        "height": win.height,
                    })
        except ImportError:
            logger.warning("pygetwindow not installed; window detection skipped")
        return windows

    def get_installed_apps_windows(self) -> List[str]:
        """Lista apps instaladas desde el Registry de Windows."""
        apps = []
        if platform.system() != "Windows":
            return apps
        try:
            import winreg
            paths = [
                r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
                r"SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
            ]
            for path in paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            if display_name:
                                apps.append(display_name)
                        except FileNotFoundError:
                            continue
                except FileNotFoundError:
                    continue
        except ImportError:
            logger.warning("winreg not available")
        return apps

    def take_snapshot(self) -> Dict[str, Any]:
        """Toma una foto del estado actual del dispositivo."""
        snapshot = {
            "platform": platform.system(),
            "active_processes": self.get_active_processes(),
            "active_windows": self.get_active_windows(),
            "installed_apps": self.get_installed_apps_windows(),
            "top_processes_by_memory": [],
            "top_processes_by_cpu": [],
        }
        procs = snapshot["active_processes"]
        if procs:
            snapshot["top_processes_by_memory"] = sorted(procs, key=lambda x: x.get("memory_mb", 0), reverse=True)[:10]
            snapshot["top_processes_by_cpu"] = sorted(procs, key=lambda x: x.get("cpu_percent", 0), reverse=True)[:10]
        self.snapshot = snapshot
        return snapshot

    def generate(self, difficulty: Optional[str] = None) -> Dict:
        if difficulty is None:
            difficulty = random.choice(["easy", "medium", "hard", "expert"])

        eligible = [t for t in DEVICE_TEMPLATES if t.get("difficulty", "medium") == difficulty]
        if not eligible:
            eligible = DEVICE_TEMPLATES

        template = random.choice(eligible)
        idx = DEVICE_TEMPLATES.index(template)
        key = self._key(idx, difficulty)

        if key in self.generated_keys:
            return self.generate(difficulty)
        self.generated_keys.add(key)

        variables = template.get("variables", {})
        question = self._fill_template(template["template"], variables)
        raw_answer = template.get("answer", "Respuesta sobre automatización de apps del dispositivo.")
        answer = self._fill_template(raw_answer, variables)

        return {
            "text": question,
            "output": answer,
            "metadata": {
                "source": "device_app_connector",
                "category": "device_automation",
                "difficulty": difficulty,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def generate_batch(
        self,
        count: int = 50,
        difficulty: Optional[str] = None,
    ) -> List[Dict]:
        results = []
        for _ in range(count):
            try:
                results.append(self.generate(difficulty))
            except Exception as exc:
                logger.debug(f"Skip device task: {exc}")
        return results

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} device samples -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    connector = DeviceAppConnector(seed=42)
    if args.snapshot:
        snap = connector.take_snapshot()
        print(json.dumps(snap, indent=2, ensure_ascii=False))
        return
    items = connector.generate_batch(count=args.count, difficulty=args.difficulty)
    output = Path(args.output)
    connector.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Device App Connector")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--difficulty", type=str, default=None, choices=["easy", "medium", "hard", "expert"])
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    p.add_argument("--snapshot", action="store_true", help="Mostrar snapshot del dispositivo y salir")
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()
