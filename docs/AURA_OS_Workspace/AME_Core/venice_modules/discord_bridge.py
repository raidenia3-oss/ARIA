#!/usr/bin/env python3
"""
INTEGRACIÓN DISCORD - CommandParser para módulos OSINT.
Procesa comandos /target, /checkip, /checkdomain y devuelve reportes estéticos.
Python 3 puro, cross-platform PC + Termux.
"""
import sys
import os
from datetime import datetime

# Importar módulos OSINT
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osint_username import check_platforms, build_report, format_for_discord
from osint_reputation import check_ip_reputation, check_domain_reputation, format_ip_report

def process_target_cmd(username):
    """Procesa /target [username] - Busca en 15 plataformas."""
    print(f"[AURA] Escaneando username: {username}...")
    results = check_platforms(username)
    report = build_report(username, results)
    formatted = format_for_discord(report)
    print("\n" + formatted)
    print(f"[AURA] Escaneo completado. {report['summary']['found']} encontrados de {report['summary']['total_checked']}")
    return report

def process_ip_cmd(ip):
    """Procesa /checkip [ip] - Verifica reputación de IP."""
    print(f"[AURA] Verificando IP: {ip}...")
    report = check_ip_reputation(ip)
    formatted = format_ip_report(report)
    print("\n" + formatted)
    print(f"[AURA] Verificación completada. {report['summary']['lists_checked']} listas consultadas.")
    return report

def process_domain_cmd(domain):
    """Procesa /checkdomain [domain] - Verifica reputación de dominio."""
    print(f"[AURA] Verificando dominio: {domain}...")
    report = check_domain_reputation(domain)
    print("\n```")
    print(f"🌐 Dominio: {domain}")
    print(f"🕐 {report['timestamp']}")
    print("")
    for check in report["checks"]:
        icon = "✅" if check.get("status") in ("resolved", "no_results") else "❌"
        print(f"  {icon} {check['type']:<20} {check.get('status', 'ok')}")
        if "ip" in check:
            print(f"     IP resuelta: {check['ip']}")
        if "server" in check:
            print(f"     Server: {check['server']}")
        if "malicious" in check:
            print(f"     Scans maliciosos: {check['malicious']}")
    print("")
    print(f"Estado: {'✅ SEGURO' if report['summary']['clean'] else '⚠️  SOSPECHOSO'}")
    print("```")
    print(f"[AURA] Verificación completada.")
    return report

def parse_and_execute(input_text):
    """Parsea un comando y ejecuta la función correspondiente."""
    parts = input_text.strip().split()
    if not parts:
        return None
    
    cmd = parts[0].lower()
    
    if cmd == "/target" and len(parts) >= 2:
        return process_target_cmd(parts[1])
    elif cmd == "/checkip" and len(parts) >= 2:
        return process_ip_cmd(parts[1])
    elif cmd == "/checkdomain" and len(parts) >= 2:
        return process_domain_cmd(parts[1])
    else:
        return {"error": "Comando no reconocido. Usa: /target [user], /checkip [ip], /checkdomain [domain]"}

def interactive_mode():
    """Modo interactivo para probar comandos."""
    print("╔═══════════════════════════════════════════╗")
    print("║  AURA OSINT - MODO INTERACTIVO           ║")
    print("║  Comandos: /target /checkip /checkdomain  ║")
    print("║  Salir: exit / quit                       ║")
    print("╚═══════════════════════════════════════════╝")
    print("")
    
    while True:
        try:
            cmd = input("OSINT> ").strip()
            if cmd.lower() in ("exit", "quit", ""):
                break
            result = parse_and_execute(cmd)
            if result and "error" in result:
                print(f"[AURA] {result['error']}")
        except KeyboardInterrupt:
            print("\n[AURA] Saliendo...")
            break
        except Exception as e:
            print(f"[AURA] Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parse_and_execute(" ".join(sys.argv[1:]))
    else:
        interactive_mode()