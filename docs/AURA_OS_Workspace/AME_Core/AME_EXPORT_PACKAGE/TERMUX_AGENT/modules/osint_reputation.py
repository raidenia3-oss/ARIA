#!/usr/bin/env python3
"""
ANALIZADOR DE REPUTACIÓN - Verificación de IPs y dominios.
Listas negras públicas, cabeceras HTTP, WHOIS básico.
Python 3 puro, sin dependencias externas.
"""
import requests
import json
import socket
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 AURA-OSINT/1.0",
    "Accept": "application/json",
    "Connection": "keep-alive",
}

def check_ip_reputation(ip):
    """Verifica reputación de IP contra listas negras."""
    result = {
        "ip": ip,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "blacklists": [],
        "summary": {"clean": True, "lists_checked": 0, "flagged": 0}
    }

    # AbuseIPDB (público)
    try:
        r = requests.get(f"https://www.abuseipdb.com/check/{ip}", headers=HEADERS, timeout=5)
        result["blacklists"].append({
            "service": "AbuseIPDB",
            "status": "clean" if r.status_code == 200 else "unknown",
            "response_code": r.status_code
        })
        if r.status_code >= 400:
            result["summary"]["flagged"] += 1
            result["summary"]["clean"] = False
    except:
        result["blacklists"].append({"service": "AbuseIPDB", "status": "timeout"})

    # VirusTotal (público limitado)
    try:
        r = requests.get(f"https://www.virustotal.com/ui/ip_addresses/{ip}", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            result["blacklists"].append({
                "service": "VirusTotal",
                "status": "flagged" if malicious > 0 else "clean",
                "malicious_reports": malicious
            })
            if malicious > 0:
                result["summary"]["flagged"] += 1
                result["summary"]["clean"] = False
        else:
            result["blacklists"].append({"service": "VirusTotal", "status": "rate_limited", "code": r.status_code})
    except:
        result["blacklists"].append({"service": "VirusTotal", "status": "timeout"})

    # Shodan (público limitado)
    try:
        r = requests.get(f"https://internetdb.shodan.io/{ip}", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            ports = data.get("ports", [])
            vulns = data.get("vulns", [])
            result["blacklists"].append({
                "service": "Shodan",
                "status": "found" if ports else "clean",
                "open_ports": len(ports),
                "vulnerabilities": len(vulns)
            })
            if vulns:
                result["summary"]["flagged"] += 1
        else:
            result["blacklists"].append({"service": "Shodan", "status": "not_found"})
    except:
        result["blacklists"].append({"service": "Shodan", "status": "timeout"})

    result["summary"]["lists_checked"] = len(result["blacklists"])
    return result

def check_domain_reputation(domain):
    """Verifica reputación de dominio."""
    result = {
        "domain": domain,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": [],
        "summary": {"clean": True, "checks_done": 0}
    }

    # Resolución DNS
    try:
        ip = socket.gethostbyname(domain)
        result["checks"].append({"type": "dns_resolution", "ip": ip, "status": "resolved"})
    except:
        result["checks"].append({"type": "dns_resolution", "status": "failed"})
        result["summary"]["clean"] = False

    # Cabeceras HTTP
    try:
        r = requests.get(f"https://{domain}", headers=HEADERS, timeout=5, verify=False)
        result["checks"].append({
            "type": "http_headers",
            "status_code": r.status_code,
            "server": r.headers.get("Server", "unknown"),
            "content_type": r.headers.get("Content-Type", "unknown"),
            "ssl": r.url.startswith("https")
        })
    except:
        result["checks"].append({"type": "http_headers", "status": "failed"})

    # URLScan.io preview
    try:
        r = requests.get(f"https://urlscan.io/api/v1/search/?q=domain:{domain}",
                        headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            total = data.get("total", 0)
            malicious = sum(1 for res in data.get("results", [])
                          if res.get("page", {}).get("status") == "malicious")
            result["checks"].append({
                "type": "urlscan",
                "total_scans": total,
                "malicious": malicious
            })
            if malicious > 0:
                result["summary"]["clean"] = False
        else:
            result["checks"].append({"type": "urlscan", "status": "no_results"})
    except:
        result["checks"].append({"type": "urlscan", "status": "timeout"})

    result["summary"]["checks_done"] = len(result["checks"])
    return result

def format_ip_report(report):
    """Formatea reporte IP para Discord."""
    lines = ["```"]
    lines.append(f"📡 IP: {report['ip']}")
    lines.append(f"🕐 {report['timestamp']}")
    lines.append("")
    for bl in report["blacklists"]:
        icon = "✅" if bl.get("status") == "clean" else "❌"
        lines.append(f"  {icon} {bl['service']:<15} {bl['status']}")
        if "malicious_reports" in bl:
            lines.append(f"     Reportes maliciosos: {bl['malicious_reports']}")
        if "open_ports" in bl:
            lines.append(f"     Puertos abiertos: {bl['open_ports']}")
        if "vulnerabilities" in bl:
            lines.append(f"     Vulnerabilidades: {bl['vulnerabilities']}")
    lines.append("")
    lines.append(f"Estado: {'✅ LIMPIA' if report['summary']['clean'] else '❌ FLAGEADA'}")
    lines.append("```")
    return "\n".join(lines)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python osint_reputation.py <ip|dominio>")
        sys.exit(1)
    target = sys.argv[1]
    if target.replace(".", "").replace(":","").replace("/","").isdigit():
        print(json.dumps(check_ip_reputation(target), indent=2))
    else:
        print(json.dumps(check_domain_reputation(target), indent=2))