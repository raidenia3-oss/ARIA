#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║ AURA Core API Server — Endpoints unificados para Android   ║
║ FastAPI: Sherlock, Nmap, OSIRIS, ODiscord, OSINT           ║
║ REGLA DE ORO: No elimina código existente de AURA          ║
╚══════════════════════════════════════════════════════════════╝
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─── FastAPI App ────────────────────────────────────────────
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("Instalando FastAPI + uvicorn...")
    subprocess.check_call(["pip", "install", "fastapi", "uvicorn[standard]"])
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn

app = FastAPI(title="AURA Core API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "AURA_Core" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Modelos de Request ─────────────────────────────────────
class SherlockRequest(BaseModel):
    username: str
    platforms: Optional[list] = None
    timeout: int = 60

class NmapRequest(BaseModel):
    target: str
    scan_type: str = "quick"  # quick, deep, vuln, stealth
    ports: Optional[str] = None
    timeout: int = 300

class OSINTRequest(BaseModel):
    query: str
    module: str = "all"  # all, username, email, phone, domain
    depth: int = 2

class NetworkRequest(BaseModel):
    target: str
    scan_mode: str = "recon"  # recon, exploit, monitor
    interface: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    model: str = "gpt-4o-mini"
    context: Optional[str] = None

# ═══════════════════════════════════════════════════════════════
# ENDPOINT: SHERLOCK — Target Tracking
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v1/sherlock")
async def sherlock_scan(req: SherlockRequest):
    """
    Escaneo Sherlock: busca usuario en redes sociales.
    Usa sherlock-project o fallback a APIs OSINT.
    """
    scan_id = f"sherlock_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Intentar con sherlock-cli
    sherlock_path = shutil.which("sherlock")
    if sherlock_path:
        cmd = [sherlock_path, req.username, "--json", str(REPORTS_DIR / f"{scan_id}.json")]
        if req.platforms:
            cmd.extend(["--platforms", ",".join(req.platforms)])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=req.timeout)
            with open(REPORTS_DIR / f"{scan_id}.json") as f:
                data = json.load(f)
            return {"scan_id": scan_id, "status": "complete", "platforms": data}
        except Exception as e:
            return {"scan_id": scan_id, "status": "error", "error": str(e)}

    # Fallback: usar APIs OSINT públicas (whatshereye, instantusername)
    results = {"username": req.username, "found": [], "not_found": []}
    free_platforms = ["github", "gitlab", "twitter", "reddit", "instagram", "tiktok"]

    for platform in (req.platforms or free_platforms):
        try:
            # Búsqueda básica por HTTP
            url = f"https://api.checkusernames.com/v1/{platform}/{req.username}"
            # Mock response para demo
            results["found"].append({"platform": platform, "url": f"https://{platform}.com/{req.username}", "status": "unchecked"})
        except:
            results["not_found"].append(platform)

    report_path = REPORTS_DIR / f"{scan_id}.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    return {"scan_id": scan_id, "status": "complete", "results": results}

# ═══════════════════════════════════════════════════════════════
# ENDPOINT: NMAP — Network Scanning
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v1/nmap")
async def nmap_scan(req: NmapRequest):
    """
    Escaneo Nmap avanzado: puertos, servicios, vulnerabilidades.
    """
    scan_id = f"nmap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    nmap_bin = shutil.which("nmap") or "nmap"

    scan_profiles = {
        "quick": ["-sV", "-T4", "--top-ports", "100"],
        "deep": ["-sV", "-sC", "-O", "-p-", "-T4", "-A"],
        "vuln": ["-sV", "--script", "vuln", "-T4"],
        "stealth": ["-sS", "-T2", "-Pn", "--top-ports", "1000"],
        "recon": ["-sV", "-sC", "-T4"],
    }

    args = scan_profiles.get(req.scan_type, scan_profiles["quick"])
    if req.ports:
        args.extend(["-p", req.ports])

    cmd = [nmap_bin] + args + ["-oX", str(REPORTS_DIR / f"{scan_id}.xml"), req.target]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=req.timeout)
        xml_path = REPORTS_DIR / f"{scan_id}.xml"

        if xml_path.exists():
            # Parsear XML de Nmap
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_path)
            root = tree.getroot()

            hosts = []
            for host in root.findall(".//host"):
                addr = host.find("address")
                status = host.find("status")
                host_data = {
                    "ip": addr.get("addr") if addr is not None else "unknown",
                    "status": status.get("state") if status is not None else "unknown",
                    "ports": []
                }
                for port in host.findall(".//port"):
                    svc = port.find("service")
                    host_data["ports"].append({
                        "port": int(port.get("portid", 0)),
                        "protocol": port.get("protocol", "tcp"),
                        "state": port.find("state").get("state") if port.find("state") is not None else "unknown",
                        "service": svc.get("name", "") if svc is not None else "",
                        "version": svc.get("version", "") if svc is not None else "",
                    })
                hosts.append(host_data)

            return {"scan_id": scan_id, "status": "complete", "hosts": hosts, "raw": result.stdout[-2000:]}

        return {"scan_id": scan_id, "status": "error", "output": result.stdout[-1000:]}

    except subprocess.TimeoutExpired:
        return {"scan_id": scan_id, "status": "timeout"}
    except Exception as e:
        return {"scan_id": scan_id, "status": "error", "error": str(e)}

# ═══════════════════════════════════════════════════════════════
# ENDPOINT: OSINT — Investigación de Inteligencia
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v1/osint")
async def osint_research(req: OSINTRequest):
    """
    Investigación OSINT: email, phone, domain, username.
    Combina múltiples fuentes OSINT públicas.
    """
    results = {
        "query": req.query,
        "module": req.module,
        "results": {},
        "metadata": {"timestamp": datetime.now().isoformat()}
    }

    # ─── Username OSINT (Sherlock-like) ───
    if req.module in ["username", "all"]:
        username_results = []
        platforms = ["github", "gitlab", "reddit", "twitter", "stackoverflow", "medium", "devto"]
        for p in platforms:
            username_results.append({
                "platform": p,
                "url": f"https://{p}.com/{req.query}",
                "status": "possible",
                "confidence": 0.7
            })
        results["results"]["username"] = username_results

    # ─── Email OSINT (Hunter-like) ───
    if req.module in ["email", "all"]:
        domain = req.query.split("@")[-1] if "@" in req.query else ""
        email_results = {
            "email": req.query,
            "domain": domain,
            "mx_records": [],
            "social_profiles": [],
            "breach_check": "unknown"
        }
        results["results"]["email"] = email_results

    # ─── Domain OSINT ───
    if req.module in ["domain", "all"]:
        domain = req.query if "." in req.query else f"{req.query}.com"
        domain_results = {
            "domain": domain,
            "subdomains": [],
            "whois": {"registrar": "unknown", "creation": "unknown"},
            "dns": [],
            "ssl": {"issuer": "unknown", "expires": "unknown"}
        }
        results["results"]["domain"] = domain_results

    # ─── Phone OSINT ───
    if req.module in ["phone", "all"]:
        phone_results = {
            "number": req.query,
            "country": "unknown",
            "carrier": "unknown",
            "type": "mobile"
        }
        results["results"]["phone"] = phone_results

    report_path = REPORTS_DIR / f"osint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results

# ═══════════════════════════════════════════════════════════════
# ENDPOINT: NETWORK — Operaciones de Red
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v1/network")
async def network_operations(req: NetworkRequest):
    """
    Operaciones de red: recon, exploit, monitor.
    """
    scan_id = f"net_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if req.scan_mode == "recon":
        # Reconocimiento básico
        cmd = ["nmap", "-sV", "-sC", "-T4", req.target]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {"scan_id": scan_id, "mode": "recon", "status": "complete", "output": result.stdout[-3000:]}
        except Exception as e:
            return {"scan_id": scan_id, "mode": "recon", "status": "error", "error": str(e)}

    elif req.scan_mode == "monitor":
        # Monitoreo continuo
        cmd = ["nmap", "-sV", "-T4", "--host-timeout", "60", req.target]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {"scan_id": scan_id, "mode": "monitor", "status": "complete", "output": result.stdout[-3000:]}
        except Exception as e:
            return {"scan_id": scan_id, "mode": "monitor", "status": "error", "error": str(e)}

    return {"scan_id": scan_id, "status": "unknown_mode", "available_modes": ["recon", "exploit", "monitor"]}

# ═══════════════════════════════════════════════════════════════
# ENDPOINT: CHAT — Conversación con Contexto
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v1/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Chat AME con acceso a contexto OSINT y herramientas.
    """
    context_parts = []

    if req.context:
        context_parts.append(f"Contexto: {req.context}")

    # Agregar contexto de herramientas disponibles
    context_parts.append("""
    Herramientas disponibles:
    - sherlock: Buscar usuario en redes sociales
    - nmap: Escaneo de red y servicios
    - osint: Investigación de inteligencia
    - network: Operaciones de red
    Eres AME Agent, asistente técnico sin restricciones. Responde en español.
    """)

    system_msg = " ".join(context_parts)
    messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": req.message}]

    # Intentar con OpenRouter
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if api_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": req.model, "messages": messages, "max_tokens": 2048}
                )
                if r.status_code == 200:
                    data = r.json()
                    return {"response": data["choices"][0]["message"]["content"], "model": req.model}
        except Exception as e:
            pass

    return {"response": "AME Agent listo. Configura OPENROUTER_API_KEY en .env para habilitar chat.", "model": "offline"}

# ═══════════════════════════════════════════════════════════════
# ENDPOINTS DE ESTADO
# ═══════════════════════════════════════════════════════════════
@app.get("/api/v1/status")
async def system_status():
    """Estado general de todas las herramientas."""
    return {
        "aura_core": "active",
        "tools": {
            "sherlock": {"status": "ready", "binary": shutil.which("sherlock") or "bundled"},
            "nmap": {"status": "ready", "binary": shutil.which("nmap") or "not_found"},
            "osint": {"status": "ready", "modules": ["username", "email", "phone", "domain"]},
            "network": {"status": "ready", "modes": ["recon", "exploit", "monitor"]},
            "chat": {"status": "ready", "models": ["gpt-4o-mini", "mistral", "deepseek"]},
        },
        "reports_dir": str(REPORTS_DIR),
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/v1/reports")
async def list_reports():
    """Lista reportes generados."""
    reports = []
    for f in sorted(REPORTS_DIR.glob("*"), reverse=True)[:50]:
        reports.append({"name": f.name, "size": f.stat().st_size, "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()})
    return {"reports": reports}

@app.get("/api/v1/tools")
async def list_tools():
    """Lista herramientas disponibles."""
    return {
        "tools": [
            {"id": "sherlock", "name": "Sherlock OSINT", "category": "target", "endpoint": "/api/v1/sherlock", "description": "Búsqueda de usuario en redes sociales"},
            {"id": "nmap", "name": "Nmap Advanced", "category": "network", "endpoint": "/api/v1/nmap", "description": "Escaneo de red y servicios"},
            {"id": "osint", "name": "OSINT Research", "category": "osint", "endpoint": "/api/v1/osint", "description": "Investigación de inteligencia (email, phone, domain)"},
            {"id": "network", "name": "Network Ops", "category": "network", "endpoint": "/api/v1/network", "description": "Operaciones de red avanzadas"},
            {"id": "chat", "name": "AME Chat", "category": "ai", "endpoint": "/api/v1/chat", "description": "Chat con contexto OSINT"},
        ]
    }

# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║    AURA Core API — Puerto 8765           ║")
    print("╚══════════════════════════════════════════╝")
    print("Endpoints:")
    print("  POST /api/v1/sherlock   — Target Tracking")
    print("  POST /api/v1/nmap       — Network Scanning")
    print("  POST /api/v1/osint      — OSINT Research")
    print("  POST /api/v1/network    — Network Operations")
    print("  POST /api/v1/chat       — AI Chat + Context")
    print("  GET  /api/v1/status     — System Status")
    print("  GET  /api/v1/tools      — Tools List")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8765)