#!/usr/bin/env python3
"""
AURA System Controller Trainer — Entrenamiento para control real del sistema.

Genera datos de entrenamiento para:
  - Comandos PowerShell / Bash seguros
  - Automatización de archivos y carpetas
  - Gestión de procesos y servicios
  - Instalación/desinstalación de software
  - Tareas programadas y mantenimiento
  - Validación y rollback de operaciones

Dataset: training-data-system.jsonl
Formato: {"text": "solicitud del usuario", "output": "comando + validación + rollback"}

Uso:
  python scripts/system_controller_trainer.py --count 100 --platform windows
  python scripts/system_controller_trainer.py --count 100 --platform linux
  python scripts/system_controller_trainer.py --category files --count 50
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SystemController")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-system.jsonl"

PLATFORMS = ["windows", "linux", "termux"]

SYSTEM_TEMPLATES: Dict[str, List[Dict]] = {
    "files": [
        {
            "template": "Crea una carpeta llamada {folder} en {location} y dentro genera {n} archivos de texto con nombres secuenciales.",
            "variables": {
                "folder": ["Proyecto_AURA", "Backup_2024", "Documentos_Cliente", "Logs_Sistema"],
                "location": ["C:\\Users\\User\\Documents", "/home/user/Documents", "C:\\Temp"],
                "n": [5, 10, 20],
            },
            "difficulty": "easy",
            "windows_cmd": "New-Item -ItemType Directory -Path '{location}\\{folder}' -Force; 1..{n} | ForEach-Object {{ New-Item -ItemType File -Path '{location}\\{folder}\\file_$_.txt' -Force }}",
            "linux_cmd": "mkdir -p '{location}/{folder}'; seq 1 {n} | xargs -I {{}} touch '{location}/{folder}/file_{{}}.txt'",
            "validation": "Verificar que existan {n} archivos en la carpeta.",
            "rollback": "Remove-Item -Path '{location}\\{folder}' -Recurse -Force (Windows) | rm -rf '{location}/{folder}' (Linux)",
        },
        {
            "template": "Busca todos los archivos {ext} en {location} que pesen más de {size} MB y muéstrame la lista ordenada por tamaño descendente.",
            "variables": {
                "ext": [".pdf", ".jpg", ".mp4", ".zip", ".log"],
                "location": ["C:\\Users\\User\\Downloads", "/home/user/Downloads", "C:\\Users\\User\\Documents"],
                "size": [10, 50, 100, 500],
            },
            "difficulty": "medium",
            "windows_cmd": "Get-ChildItem -Path '{location}' -Filter '*{ext}' -Recurse | Where-Object {{ $_.Length -gt {size}MB }} | Sort-Object Length -Descending | Select-Object FullName, @{{N='SizeMB';E={{[math]::Round($_.Length/1MB,2)}}}}",
            "linux_cmd": "find '{location}' -name '*{ext}' -size +{size}M -exec ls -lh {{}} \\; | sort -k5 -h -r",
            "validation": "Confirmar que todos los resultados superan el tamaño especificado.",
            "rollback": "No aplica (solo lectura).",
        },
        {
            "template": "Comprime todos los archivos de {location} en un ZIP llamado {zip_name} con contraseña 'AURA2024'.",
            "variables": {
                "location": ["C:\\Users\\User\\Documents\\Proyecto", "/home/user/Documents/Proyecto"],
                "zip_name": ["backup_proyecto.zip", "documentos_comprimidos.zip"],
            },
            "difficulty": "medium",
            "windows_cmd": "Compress-Archive -Path '{location}\\*' -DestinationPath '{location}\\..\\{zip_name}' -Password (ConvertTo-SecureString 'AURA2024' -AsPlainText -Force)",
            "linux_cmd": "zip -r -P AURA2024 '{zip_name}' '{location}'",
            "validation": "Verificar que el ZIP se creó y tiene protección con contraseña.",
            "rollback": "Remove-Item '{zip_name}' (Windows) | rm '{zip_name}' (Linux)",
        },
    ],
    "processes": [
        {
            "template": "Lista todos los procesos que consumen más de {cpu}% CPU y termina los 3 más altos, guardando el reporte en {report_path}.",
            "variables": {
                "cpu": [80, 90, 95],
                "report_path": ["C:\\Users\\User\\Documents\\cpu_report.txt", "/home/user/Documents/cpu_report.txt"],
            },
            "difficulty": "medium",
            "windows_cmd": "Get-Process | Where-Object {{ $_.CPU -gt {cpu} }} | Sort-Object CPU -Descending | Select-Object -First 3 | Format-Table > '{report_path}'; Get-Process | Where-Object {{ $_.CPU -gt {cpu} }} | Sort-Object CPU -Descending | Select-Object -First 3 | Stop-Process -Force",
            "linux_cmd": "ps aux --sort=-%cpu | awk 'NR==1 || $3 > {cpu}' | head -n 4 > '{report_path}'; ps aux --sort=-%cpu | awk 'NR>1 && $3 > {cpu}' | head -n 3 | awk '{{print $2}}' | xargs kill -9",
            "validation": "Verificar que los procesos terminados ya no aparecen en top/Get-Process.",
            "rollback": "No aplica (procesos terminados).",
        },
        {
            "template": "Reinicia el servicio {service} y verifica que quede en estado 'running'.",
            "variables": {
                "service": ["wuauserv", "Spooler", "Docker", "nginx", "postgresql"],
            },
            "difficulty": "easy",
            "windows_cmd": "Restart-Service -Name '{service}' -Force; Get-Service -Name '{service}' | Select-Object Name, Status",
            "linux_cmd": "sudo systemctl restart '{service}'; sudo systemctl is-active '{service}'",
            "validation": "El servicio debe mostrar Status: Running / active.",
            "rollback": "Start-Service -Name '{service}' (Windows) | sudo systemctl start '{service}' (Linux)",
        },
    ],
    "software": [
        {
            "template": "Instala {software} usando el gestor de paquetes oficial y verifica la instalación.",
            "variables": {
                "software": ["Python 3.12", "Node.js 20", "Docker Desktop", "Git", "VSCode"],
            },
            "difficulty": "medium",
            "windows_cmd": "winget install --id {software} --accept-package-agreements --accept-source-agreements; {software} --version",
            "linux_cmd": "sudo apt update && sudo apt install -y {software}; {software} --version",
            "validation": "Ejecutar '{software} --version' y confirmar versión instalada.",
            "rollback": "winget uninstall {software} (Windows) | sudo apt remove {software} (Linux)",
        },
        {
            "template": "Desinstala {software} y limpia archivos residuales en {location}.",
            "variables": {
                "software": ["Node.js", "Python 3.11", "Docker Desktop"],
                "location": ["C:\\Program Files", "/usr/local", "C:\\Users\\User\\AppData"],
            },
            "difficulty": "medium",
            "windows_cmd": "winget uninstall --id {software}; Remove-Item -Path '{location}\\{software}' -Recurse -Force -ErrorAction SilentlyContinue",
            "linux_cmd": "sudo apt remove --purge -y {software}; rm -rf '{location}/{software}'",
            "validation": "Verificar que el ejecutable ya no existe en PATH.",
            "rollback": "Reinstalar con gestor de paquetes.",
        },
    ],
    "scheduling": [
        {
            "template": "Crea una tarea programada para ejecutar {script} todos los días a las {hour}:{minute} con privilegios elevados.",
            "variables": {
                "script": ["C:\\Scripts\\backup.ps1", "/home/user/scripts/backup.sh"],
                "hour": [2, 3, 6, 22],
                "minute": [0, 15, 30, 45],
            },
            "difficulty": "hard",
            "windows_cmd": "$action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument '-File {script}'; $trigger = New-ScheduledTaskTrigger -Daily -At '{hour}:{minute}'; Register-ScheduledTask -TaskName 'AURA_{script}' -Action $action -Trigger $trigger -User 'SYSTEM' -RunLevel Highest -Force",
            "linux_cmd": "(crontab -l 2>/dev/null; echo '{minute} {hour} * * * {script}') | crontab -",
            "validation": "Verificar tarea en Task Scheduler (Windows) o crontab -l (Linux).",
            "rollback": "Unregister-ScheduledTask -TaskName 'AURA_{script}' -Confirm:$false (Windows) | crontab -r (Linux)",
        },
    ],
    "security": [
        {
            "template": "Analiza los logs de seguridad de Windows Event Log y detecta intentos de login fallidos en las últimas {hours} horas.",
            "variables": {
                "hours": [1, 6, 24],
            },
            "difficulty": "hard",
            "windows_cmd": "Get-WinEvent -LogName Security -MaxEvents 1000 | Where-Object {{ $_.Id -eq 4625 -and $_.TimeCreated -gt (Get-Date).AddHours(-{hours}) }} | Select-Object TimeCreated, Message | Format-List",
            "linux_cmd": "sudo journalctl -u sshd --since '{hours} hours ago' | grep 'Failed password'",
            "validation": "Contar intentos fallidos y reportar IPs origen.",
            "rollback": "No aplica (solo lectura).",
        },
        {
            "template": "Configura el firewall de Windows para bloquear todas las conexiones entrantes excepto el puerto {port} (TCP) y {port2} (UDP).",
            "variables": {
                "port": [22, 80, 443, 8080],
                "port2": [53, 123, 5000],
            },
            "difficulty": "hard",
            "windows_cmd": "Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block; New-NetFirewallRule -DisplayName 'Allow TCP {port}' -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow; New-NetFirewallRule -DisplayName 'Allow UDP {port2}' -Direction Inbound -Protocol UDP -LocalPort {port2} -Action Allow",
            "linux_cmd": "sudo ufw default deny incoming; sudo ufw allow {port}/tcp; sudo ufw allow {port2}/udp; sudo ufw enable",
            "validation": "Verificar reglas activas con Get-NetFirewallRule (Windows) | sudo ufw status (Linux).",
            "rollback": "Remove-NetFirewallRule -DisplayName 'Allow TCP {port}' (Windows) | sudo ufw delete allow {port}/tcp (Linux)",
        },
    ],
}


class SystemControllerTrainer:
    """Genera datos de entrenamiento para control del sistema."""

    def __init__(self, platform: str = "windows", seed: int = 42):
        self.platform = platform
        random.seed(seed)
        self.generated_keys: set = set()

    def _key(self, category: str, idx: int) -> str:
        return f"{category}:{idx}:{self.platform}"

    def _fill(self, template: str, variables: Dict) -> str:
        result = template
        for var, values in variables.items():
            if isinstance(values, list) and values:
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                result = result.replace("{" + var + "}", val)
        return result

    def generate(self, category: Optional[str] = None, difficulty: Optional[str] = None) -> Dict:
        categories = [category] if category else list(SYSTEM_TEMPLATES.keys())
        templates = []
        for cat in categories:
            templates.extend(SYSTEM_TEMPLATES.get(cat, []))

        if not templates:
            raise ValueError("No templates available")

        if difficulty:
            templates = [t for t in templates if t.get("difficulty", "medium") == difficulty] or templates

        template = random.choice(templates)
        idx = SYSTEM_TEMPLATES.get(category, templates).index(template) if category else random.randint(0, 1000)
        key = self._key(category or "mixed", idx)

        if key in self.generated_keys:
            return self.generate(category, difficulty)
        self.generated_keys.add(key)

        question = self._fill(template["template"], template.get("variables", {}))
        cmd_key = "windows_cmd" if self.platform == "windows" else "linux_cmd"
        command = self._fill(template.get(cmd_key, ""), template.get("variables", {}))
        validation = self._fill(template.get("validation", ""), template.get("variables", {}))
        rollback = self._fill(template.get("rollback", ""), template.get("variables", {}))

        return {
            "text": question,
            "output": f"Comando ({self.platform}):\n{command}\n\nValidación:\n{validation}\n\nRollback:\n{rollback}",
            "metadata": {
                "source": "system_controller",
                "category": category or "mixed",
                "platform": self.platform,
                "difficulty": template.get("difficulty", "medium"),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def generate_batch(self, count: int = 50, category: Optional[str] = None, difficulty: Optional[str] = None) -> List[Dict]:
        results = []
        for _ in range(count):
            try:
                results.append(self.generate(category, difficulty))
            except Exception as exc:
                logger.debug(f"Skip system task: {exc}")
        return results

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} system samples -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    trainer = SystemControllerTrainer(platform=args.platform)
    items = trainer.generate_batch(count=args.count, category=args.category, difficulty=args.difficulty)
    output = Path(args.output)
    trainer.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA System Controller Trainer")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--platform", type=str, default="windows", choices=PLATFORMS)
    p.add_argument("--category", type=str, default=None, choices=list(SYSTEM_TEMPLATES.keys()))
    p.add_argument("--difficulty", type=str, default=None, choices=["easy", "medium", "hard", "expert"])
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()
