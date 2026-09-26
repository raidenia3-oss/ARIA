#!/usr/bin/env python3
"""
Test script para verificar el módulo Venice Shodan Scanner.
"""

import os
import sys
import json

# Añadir AURA_Core al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from venice_shodan_scanner import VeniceShodanScanner


def test_scanner():
    """Prueba básica del escáner."""
    print("🧪 Probando VeniceShodanScanner...")
    
    # Verificar que la clase se puede instanciar
    scanner = VeniceShodanScanner()
    print(f"✅ Scanner instanciado: {scanner}")
    print(f"   API Key configurada: {'Sí' if scanner.api_key else 'No (usando env var)'}")
    
    # Probar resolución de target
    print("\n🔍 Probando resolución de target...")
    ip = scanner._resolve_target("8.8.8.8")
    print(f"   IP 8.8.8.8 -> {ip}")
    
    ip = scanner._resolve_target("google.com")
    print(f"   google.com -> {ip}")
    
    # Probar formateo para Discord
    print("\n📋 Probando formateo para Discord embed...")
    mock_result = {
        "ip": "8.8.8.8",
        "timestamp": "2026-06-04T20:00:00Z",
        "open_ports": [
            {"port": 53, "protocol": "udp", "service": "dns", "version": "", "banner": ""},
            {"port": 443, "protocol": "tcp", "service": "https", "version": "nginx", "banner": "HTTP/1.1 200 OK"}
        ],
        "critical_vulnerabilities": [
            {"cve": "CVE-2023-1234", "cvss": 9.8, "summary": "Critical vulnerability in DNS server"}
        ],
        "geolocation": {
            "country": "United States",
            "country_code": "US",
            "city": "Mountain View",
            "region": "CA",
            "coordinates": [-122.0838, 37.3860],
            "isp": "Google LLC",
            "org": "Google LLC",
            "asn": "AS15169"
        },
        "summary": {
            "total_ports": 2,
            "critical_vulns": 1,
            "country": "United States",
            "org": "Google LLC"
        }
    }
    
    embed = scanner.format_for_discord_embed(mock_result)
    print(f"   Título: {embed['title']}")
    print(f"   Color: {hex(embed['color'])}")
    print(f"   Fields: {len(embed['fields'])}")
    for field in embed['fields']:
        print(f"     - {field['name']}: {field['value'][:50]}...")
    
    # Probar respuesta de error
    print("\n❌ Probando respuesta de error...")
    error_result = {"ip": "1.2.3.4", "error": "API Key inválida"}
    error_embed = scanner.format_for_discord_embed(error_result)
    print(f"   Título: {error_embed['title']}")
    print(f"   Color: {hex(error_embed['color'])}")
    
    print("\n✅ Todas las pruebas básicas pasaron!")
    print("\n📝 Para probar con API real, configura SHODAN_API_KEY y ejecuta:")
    print("   python -m venice_shodan_scanner 8.8.8.8 --mode host --output discord")


if __name__ == "__main__":
    test_scanner()