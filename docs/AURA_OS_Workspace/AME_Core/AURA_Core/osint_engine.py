"""
OSINT Engine v2 — AURA
Wrapper para PhoneInfoga y Mr. Holmes con soporte para:
  - Ejecución asíncrona en segundo plano (subprocess Popen)
  - Recepción de comandos vía Flask/API REST
  - Resultados capturados en JSON
"""
import subprocess
import json
import sys
import os
import threading
import time
import psutil  # opcional: para matar procesos hijos si es necesario

class OSINTEngine:
    """Wrapper mejorado para PhoneInfoga y Mr. Holmes con control de procesos."""

    def __init__(self, phoneinfoga_path=None, mrholmes_path=None):
        self.phoneinfoga_path = phoneinfoga_path or self._find_tool("phoneinfoga")
        self.mrholmes_path    = mrholmes_path    or self._find_tool("mrholmes")
        self._active_processes = {}  # {task_id: proc}
        self._results_cache   = {}  # {task_id: result_dict}
        self._lock = threading.Lock()

    # ────────────────────────── helpers ──────────────────────────

    @staticmethod
    def _find_tool(name):
        """Busca el binario en PATH o devuelve el nombre por defecto."""
        import shutil
        path = shutil.which(name)
        return path if path else name

    def _run_sync(self, command, timeout=60):
        """Ejecuta un comando síncrono y devuelve stdout/stderr."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return result.stdout
            else:
                return f"[stderr]\n{result.stderr}\n[stdout]\n{result.stdout}"
        except subprocess.TimeoutExpired:
            return "[ERROR] Timeout alcanzado (60s)"
        except Exception as e:
            return f"[ERROR] {str(e)}"

    # ──────────────────── comandos OSINT ────────────────────

    def scan_phone(self, phone_number):
        """PhoneInfoga scan de número telefónico."""
        print(f"🔍 [OSINT] PhoneInfoga -> {phone_number}")
        cmd = f"{self.phoneinfoga_path} scan -n {phone_number}"
        output = self._run_sync(cmd)
        return {
            "tool": "PhoneInfoga",
            "target": phone_number,
            "status": "completed",
            "result": output
        }

    def scan_email(self, email):
        """Mr. Holmes análisis de email."""
        print(f"🔍 [OSINT] MrHolmes -> {email}")
        cmd = f"{self.mrholmes_path} {email}"
        output = self._run_sync(cmd)
        return {
            "tool": "MrHolmes",
            "target": email,
            "status": "completed",
            "result": output
        }

    def scan_phone_async(self, phone_number, task_id=None):
        """Lanza PhoneInfoga en un hilo separado (no bloqueante)."""
        task_id = task_id or f"phone_{int(time.time())}"
        def _worker():
            result = self.scan_phone(phone_number)
            with self._lock:
                self._results_cache[task_id] = result
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        with self._lock:
            self._active_processes[task_id] = t
        return {"task_id": task_id, "status": "running", "tool": "PhoneInfoga", "target": phone_number}

    def scan_email_async(self, email, task_id=None):
        """Lanza Mr. Holmes en un hilo separado."""
        task_id = task_id or f"email_{int(time.time())}"
        def _worker():
            result = self.scan_email(email)
            with self._lock:
                self._results_cache[task_id] = result
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        with self._lock:
            self._active_processes[task_id] = t
        return {"task_id": task_id, "status": "running", "tool": "MrHolmes", "target": email}

    def get_result(self, task_id):
        """Recupera el resultado de una tarea asíncrona."""
        with self._lock:
            if task_id in self._results_cache:
                res = self._results_cache.pop(task_id)
                self._active_processes.pop(task_id, None)
                return res
            elif task_id in self._active_processes:
                return {"task_id": task_id, "status": "running"}
            else:
                return {"error": "task_id no encontrado"}

    def execute(self, tool, target, sync=True):
        """
        Interfaz unificada.
        sync=True  → bloqueante, devuelve resultado completo.
        sync=False → lanza en hilo, devuelve task_id.
        """
        if tool == "phone":
            if sync:
                return self.scan_phone(target)
            return self.scan_phone_async(target)
        elif tool == "email":
            if sync:
                return self.scan_email(target)
            return self.scan_email_async(target)
        else:
            return {"error": f"Herramienta no soportada: {tool}. Use 'phone' o 'email'."}

    def list_tasks(self):
        """Devuelve los IDs de tareas activas."""
        with self._lock:
            return {tid: "running" for tid in self._active_processes if isinstance(self._active_processes[tid], threading.Thread) and self._active_processes[tid].is_alive()}


# ──────────────────────── CLI ────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AURA OSINT Engine")
    parser.add_argument("--tool", required=True, choices=["phone", "email"])
    parser.add_argument("--target", required=True)
    parser.add_argument("--async", action="store_true", dest="async_mode", help="Ejecutar en segundo plano")
    args = parser.parse_args()

    engine = OSINTEngine()
    result = engine.execute(args.tool, args.target, sync=not args.async_mode)
    print(json.dumps(result, indent=2, ensure_ascii=False))