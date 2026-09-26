#!/usr/bin/env python3
"""
tool_router.py - FASE 31: AURA Penetration Workspace Router
Gestor de herramientas de red/scraping bajo demanda.
Inicializa binarios/herramientas solo al solicitar (regla: cero procesos innecesarios).
Logs en crudo por WS a EventManager. Resultados -> KnowledgeGraph (Fase 18).
"""

import shutil
import subprocess
import sys
import time
import logging
import threading
import json
from typing import Any, Dict, Optional

logger = logging.getLogger("AURA_PenWorkspace")


# Referencia perezosa a EventManager/KG para evitar ciclos fuertes
def _get_event_manager():
    from AURA_Core.event_manager import EventManager

    return EventManager(
        config={"rules_file": "rules.json", "telemetry_file": "telemetry_history.json"}
    )


def _get_knowledge_graph():
    try:
        from AURA_Core.memory.knowledge_graph import KnowledgeGraph

        return KnowledgeGraph()
    except Exception:
        return None


class ToolRouter:
    """
    Router de herramientas tácticas.
    - Lazy init: solo carga/instala al invocar.
    - Autodependencias: detecta ausencia y ofrece ruta de instalación.
    - Bare-metal logging: WS hacia EventManager como texto plano.
    - KnowledgeGraph: persiste hallazgos (puertos/IPs/selectores).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def request(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solicita ejecutar una herramienta.
        tool: 'nmap' | 'mitmproxy' | 'scapy' | 'requests' | ...
        args: parámetros específicos (targets, opts, etc.)
        """
        tool = (tool or "").lower().strip()
        if not tool:
            return {"ok": False, "error": "tool vacío"}

        with self._lock:
            if not self._loaded.get(tool, False):
                ready = self._ensure_tool(tool)
                if not ready:
                    return {
                        "ok": False,
                        "error": f"Herramienta no disponible: {tool}",
                        "install_hint": self._install_hint(tool),
                    }
                self._loaded[tool] = True

        # Enrutar ejecución
        try:
            handler = getattr(self, f"_run_{tool}", None)
            if handler is None:
                return {"ok": False, "error": f"Sin handler para {tool}"}
            result = handler(args)
            self._log_raw(tool, result)
            self._store_in_graph(tool, args, result)
            return {"ok": True, "result": result}
        except Exception as e:
            self._log_raw(tool, {"ERROR": str(e)})
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Lazy load / autodependencias
    # ------------------------------------------------------------------
    def _ensure_tool(self, tool: str) -> bool:
        if tool in ("requests", "scapy"):
            try:
                __import__(tool)
                return True
            except Exception:
                return self._pip_install(tool)

        if tool == "nmap":
            return shutil.which("nmap") is not None

        if tool == "mitmproxy":
            return shutil.which("mitmproxy") is not None

        # Por defecto: asumir False para herramientas desconocidas
        return False

    def _pip_install(self, pkg: str) -> bool:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            return True
        except Exception as e:
            logger.error(f"pip install {pkg} fallo: {e}")
            return False

    @staticmethod
    def _install_hint(tool: str) -> str:
        if tool in ("requests", "scapy"):
            return f"pip install {tool}"
        if tool == "nmap":
            return "Instalar nmap (Windows: choco install nmap; Linux: apt install nmap)"
        if tool == "mitmproxy":
            return "Instalar mitmproxy (pip install mitmproxy) o descargar binario"
        return "Herramienta no reconocida"

    # ------------------------------------------------------------------
    # Logging bare-metal por WS a EventManager (texto plano, veloz)
    # ------------------------------------------------------------------
    def _log_raw(self, tool: str, payload: Dict[str, Any]) -> None:
        line = json.dumps({"tool": tool, "payload": payload}, ensure_ascii=False)
        try:
            em = _get_event_manager()
            em.broadcast({"tipo": "pen_log", "data": line, "ts": time.time()})
        except Exception as e:
            logger.error(f"WS broadcast error: {e}")

    # ------------------------------------------------------------------
    # Persistencia en Grafo (Fase 18)
    # ------------------------------------------------------------------
    def _store_in_graph(self, tool: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
        kg = _get_knowledge_graph()
        if kg is None:
            return
        try:
            # Nodo central: herramienta ejecutada
            kg_center = f"tool:{tool}"
            kg.add_node(
                kg_center,
                {
                    "type": "pen_tool",
                    "tool": tool,
                    "ran_at": time.time(),
                },
            )

            # Relaciones según tipo de hallazgo
            try:
                if tool == "nmap":
                    hosts = result.get("hosts", [])
                    for h in hosts:
                        ip = h.get("address", {}).get("addr") if isinstance(h, dict) else str(h)
                        if not ip:
                            continue
                        node_id = f"host:{ip}"
                        kg.add_node(node_id, {"type": "host", "address": ip})
                        kg.add_edge(
                            kg_center,
                            node_id,
                            {"relation": "scanned", "ports": h.get("ports", [])},
                        )

                elif tool == "scapy":
                    targets = args.get("targets", [])
                    for t in targets:
                        node_id = f"target:{t}"
                        kg.add_node(node_id, {"type": "scapy_target", "value": t})
                        kg.add_edge(kg_center, node_id, {"relation": "probed"})

                elif tool in ("requests", "scraping"):
                    selectors = []
                    if isinstance(result, dict):
                        selectors = result.get("selectors", [])
                    for sel in selectors:
                        node_id = f"selector:{sel}"
                        kg.add_node(node_id, {"type": "web_selector", "value": sel})
                        kg.add_edge(kg_center, node_id, {"relation": "discovered"})

                kg._save()
            except Exception as e:
                logger.error(f"KnowledgeGraph persist error: {e}")
        except Exception as e:
            logger.error(f"KnowledgeGraph persist error: {e}")

    # ------------------------------------------------------------------
    # Handlers por herramienta (ejecución real, minimalista)
    # ------------------------------------------------------------------
    def _run_nmap(self, args: Dict[str, Any]) -> Dict[str, Any]:
        target = args.get("target") or args.get("targets", "")
        opts = args.get("opts", "-sT -p- -T4 --open")
        if not target:
            return {"hosts": [], "raw": "missing target"}

        cmd = ["nmap", *opts.split(), str(target)]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=120)
            return {"hosts": _parse_nmap(out), "raw": out[:4000]}
        except subprocess.CalledProcessError as e:
            return {"hosts": [], "raw": e.output[:4000], "rc": e.returncode}
        except Exception as e:
            return {"hosts": [], "raw": str(e)}

    def _run_scapy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        import scapy.all as scapy

        targets = args.get("targets", [])
        if isinstance(targets, str):
            targets = [targets]
        if not targets:
            return {"packets": 0}

        pkts = []
        for t in targets:
            try:
                # SYN sweep ligero sin flood
                ans, _ = scapy.sr(
                    scapy.IP(dst=t) / scapy.TCP(dport=80, flags="S"), timeout=2, verbose=0
                )
                pkts.append({"target": t, "answered": len(ans)})
            except Exception as e:
                pkts.append({"target": t, "error": str(e)})
        return {"packets": len(pkts), "details": pkts}

    def _run_requests(self, args: Dict[str, Any]) -> Dict[str, Any]:
        import requests as req

        url = args.get("url")
        if not url:
            return {"status": "error", "error": "url faltante"}
        try:
            r = req.get(url, timeout=15, allow_redirects=True)
            return {
                "status": r.status_code,
                "final_url": r.url,
                "headers": dict(r.headers),
                "selectors": _extract_selectors(r.text),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_mitmproxy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # No corre interactive: solo valida y devuelve la ruta del binario.
        path = shutil.which("mitmproxy") or ""
        return {
            "ok": bool(path),
            "binary": path,
            "note": "mitmproxy no se ejecuta en modo interactivo desde ToolRouter.",
        }


# ------------------------------------------------------------------
# Parsers mínimos (sin dependencias pesadas)
# ------------------------------------------------------------------
def _parse_nmap(raw: str) -> list:
    hosts = []
    current: Dict[str, Any] = {}
    for line in raw.splitlines():
        if line.startswith("Nmap scan report for "):
            if current.get("address"):
                hosts.append(current)
            current = {"address": line.split("for ", 1)[1].strip(), "ports": []}
        elif "open" in line and current:
            parts = line.split()
            port_info = {"port": parts[0], "state": parts[1], "service": " ".join(parts[2:])}
            current["ports"].append(port_info)
    if current.get("address"):
        hosts.append(current)
    return hosts


def _extract_selectors(html: str) -> list:
    selectors = []
    for token in ["id=", "class=", "data-"]:
        idx = html.lower().find(token)
        while idx != -1 and len(selectors) < 20:
            start = idx
            end = html.find('"', start + len(token))
            if end == -1:
                end = start + 120
            selectors.append(html[start:end].strip())
            idx = html.lower().find(token, end)
    return selectors


# Singleton
tool_router = ToolRouter()

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("tool")
    p.add_argument("--args", default="{}")
    a = p.parse_args()
    out = tool_router.request(a.tool, json.loads(a.args))
    print(json.dumps(out, ensure_ascii=False, indent=2))
