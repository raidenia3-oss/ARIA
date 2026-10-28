"""ARIA security research sandbox (simulated, non-destructive)."""
import os
import subprocess


def sandbox_status():
    return {
        "sandbox": "ARIA-SEC-SIM",
        "mode": "simulation",
        "real_network": False,
        "real_targets": False,
        "note": "Solo entorno simulado. No se ejecutan ataques reales.",
    }


def local_suspicious_scan():
    procs = []
    try:
        out = subprocess.check_output(["tasklist"], text=True, stderr=subprocess.DEVNULL, timeout=15)
        for line in out.splitlines()[3:]:
            if line.strip():
                procs.append(line.split()[0])
    except Exception as exc:
        return {"error": str(exc)}
    suspicious = [p for p in set(procs) if any(k in p.lower() for k in ("miner", "crypt", "keylog", "trojan", "ransom"))]
    return {"process_count": len(set(procs)), "suspicious": suspicious}


def countermeasures():
    return [
        "Aislar proceso sospechoso (solo PID verificado).",
        "Bloquear salida de red no autorizada.",
        "Rotar credenciales expuestas.",
        "Restaurar desde backup verificado.",
        "Registrar incidente en auditoria.",
    ]
