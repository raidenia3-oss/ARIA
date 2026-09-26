#!/usr/bin/env python3
"""
venice_shodan_scanner.py - Módulo Venice OSINT para escaneo Shodan autónomo.
Parte del ciclo de ciberinteligencia: Recolección -> Procesamiento -> Análisis.

Este módulo:
1. Usa únicamente 'requests' (sin dependencias extra) para compatibilidad con Termux
2. Consulta la API de Shodan (host, search, vulnerabilities)
3. FILTRA BASURA: Solo guarda IP, Puertos Abiertos, Vulnerabilidades Críticas, Geolocalización
4. Devuelve estructura JSON limpia para Discord embeds

Autor: AURA System
Fecha: 2026
"""

import os
import sys
import json
import logging
import requests
import socket
from typing import Dict, List, Optional, Any
from datetime import datetime

# Configuración de logging - cross-platform
import platform
import os

# Determinar directorio de logs según plataforma
if platform.system() == "Linux" and os.path.exists("/sdcard"):
    log_path = "/sdcard/venice_shodan.log"
else:
    log_path = os.path.join(os.path.dirname(__file__), "venice_shodan.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("VeniceShodanScanner")


class VeniceShodanScanner:
    """
    Escáner Shodan para módulos Venice.
    Usa solo requests (stdlib compatible) para evitar fallos en Termux.
    """
    
    SHODAN_BASE_URL = "https://api.shodan.io"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el escáner.
        
        Args:
            api_key: Clave API de Shodan. Si no se proporciona, busca en SHODAN_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("SHODAN_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "AURA-Venice-Shodan/1.0"})
        
        if not self.api_key:
            logger.warning("SHODAN_API_KEY no configurada. Algunas funciones no estarán disponibles.")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Hace una petición a la API de Shodan con manejo de errores.
        """
        if not self.api_key:
            return {"error": "SHODAN_API_KEY no configurada"}
        
        url = f"{self.SHODAN_BASE_URL}{endpoint}"
        request_params = {"key": self.api_key}
        if params:
            request_params.update(params)
        
        try:
            logger.info(f"Consultando Shodan: {endpoint}")
            response = self.session.get(url, params=request_params, timeout=30)
            
            if response.status_code == 401:
                return {"error": "API Key inválida o sin permisos"}
            elif response.status_code == 404:
                return {"error": "No se encontraron resultados"}
            elif response.status_code == 429:
                return {"error": "Rate limit excedido"}
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("Timeout consultando Shodan")
            return {"error": "Timeout en la petición"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red: {e}")
            return {"error": f"Error de red: {str(e)}"}
        except json.JSONDecodeError:
            logger.error("Respuesta no es JSON válido")
            return {"error": "Respuesta inválida del servidor"}
    
    def _resolve_target(self, target: str) -> str:
        """
        Resuelve un dominio a IP si es necesario.
        """
        try:
            socket.inet_aton(target)
            return target  # Ya es una IP
        except socket.error:
            # Es un dominio, resolver
            try:
                ip = socket.gethostbyname(target)
                logger.info(f"Resuelto {target} -> {ip}")
                return ip
            except socket.gaierror:
                logger.error(f"No se pudo resolver: {target}")
                return target  # Devolver original para que falle en la API
    
    def scan_host(self, target: str) -> Dict:
        """
        Escanea un host (IP o dominio) usando Shodan Host API.
        Retorna estructura limpia: IP, Puertos, Vulnerabilidades Críticas, Geo.
        
        FASE 3 - PROCESAMIENTO DE BASURA: Filtra solo lo relevante.
        """
        ip = self._resolve_target(target)
        data = self._make_request(f"/shodan/host/{ip}")
        
        if "error" in data:
            return self._error_response(target, data["error"])
        
        # FILTRADO FASE 3: Solo campos relevantes
        return self._clean_host_data(data, target)
    
    def search(self, query: str, limit: int = 10) -> Dict:
        """
        Búsqueda general en Shodan (ej: "apache country:PE port:80").
        Retorna lista de hosts con estructura limpia.
        """
        data = self._make_request("/shodan/host/search", {"query": query, "limit": limit})
        
        if "error" in data:
            return {"error": data["error"], "matches": []}
        
        # Filtrar cada match
        clean_matches = []
        for match in data.get("matches", [])[:limit]:
            clean_matches.append(self._clean_host_data(match))
        
        return {
            "query": query,
            "total": data.get("total", 0),
            "matches": clean_matches
        }
    
    def get_vulnerabilities(self, target: str) -> Dict:
        """
        Obtiene vulnerabilidades (CVEs) expuestas de un host.
        """
        ip = self._resolve_target(target)
        
        # Usar search con filtro de IP para obtener vulns
        query = f"ip:{ip}"
        data = self._make_request("/shodan/host/search", {"query": query, "limit": 1})
        
        if "error" in data:
            return {"error": data["error"], "vulnerabilities": []}
        
        matches = data.get("matches", [])
        if not matches:
            return {"ip": ip, "vulnerabilities": []}
        
        host_data = matches[0]
        vulns = host_data.get("vulns", {})
        
        # Filtrar solo CVEs críticos/altos (CVSS >= 7.0)
        critical_vulns = []
        for cve_id, cve_data in vulns.items():
            cvss = cve_data.get("cvss", 0)
            if cvss >= 7.0:
                critical_vulns.append({
                    "cve": cve_id,
                    "cvss": cvss,
                    "summary": cve_data.get("summary", "")[:200]  # Truncar
                })
        
        return {
            "ip": ip,
            "vulnerabilities": critical_vulns,
            "total_found": len(vulns),
            "critical_count": len(critical_vulns)
        }
    
    def _clean_host_data(self, raw: Dict, original_target: str = "") -> Dict:
        """
        FASE 3 - PROCESAMIENTO DE BASURA:
        Filtra el JSON crudo de Shodan y retorna SOLO:
        - IP
        - Puertos Abiertos (con servicio/versión)
        - Vulnerabilidades Críticas (CVSS >= 7.0)
        - Geolocalización (país, ciudad, org, ISP, coords)
        """
        ip = raw.get("ip_str", original_target)
        
        # 1. PUERTOS ABIERTOS - solo los abiertos con info útil
        open_ports = []
        for port_info in raw.get("data", []):
            port = port_info.get("port")
            transport = port_info.get("transport", "tcp")
            product = port_info.get("product", "")
            version = port_info.get("version", "")
            service = port_info.get("_shodan", {}).get("module", "")
            
            if port:
                open_ports.append({
                    "port": port,
                    "protocol": transport,
                    "service": service or product,
                    "version": version,
                    "banner": port_info.get("data", "")[:100]  # Primeros 100 chars
                })
        
        # 2. VULNERABILIDADES CRÍTICAS (CVSS >= 7.0)
        critical_vulns = []
        for cve_id, cve_data in raw.get("vulns", {}).items():
            cvss = cve_data.get("cvss", 0)
            if cvss >= 7.0:
                critical_vulns.append({
                    "cve": cve_id,
                    "cvss": cvss,
                    "summary": cve_data.get("summary", "")[:200]
                })
        
        # 3. GEOLOCALIZACIÓN
        location = raw.get("location", {})
        geo = {
            "country": location.get("country_name", ""),
            "country_code": location.get("country_code", ""),
            "city": location.get("city", ""),
            "region": location.get("region_code", ""),
            "coordinates": [
                location.get("longitude", 0),
                location.get("latitude", 0)
            ],
            "isp": raw.get("isp", ""),
            "org": raw.get("org", ""),
            "asn": raw.get("asn", "")
        }
        
        # 4. ESTRUCTURA LIMPIA FINAL
        return {
            "ip": ip,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "open_ports": open_ports,
            "critical_vulnerabilities": critical_vulns,
            "geolocation": geo,
            "summary": {
                "total_ports": len(open_ports),
                "critical_vulns": len(critical_vulns),
                "country": geo["country"],
                "org": geo["org"]
            }
        }
    
    def _error_response(self, target: str, error: str) -> Dict:
        """Respuesta de error estandarizada."""
        return {
            "ip": target,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": error,
            "open_ports": [],
            "critical_vulnerabilities": [],
            "geolocation": {},
            "summary": {"total_ports": 0, "critical_vulns": 0}
        }
    
    def format_for_discord_embed(self, scan_result: Dict) -> Dict:
        """
        Formatea el resultado para un embed de Discord.
        Retorna dict con title, description, fields, color, etc.
        """
        if "error" in scan_result:
            return {
                "title": "❌ Error en Escaneo Shodan",
                "description": f"Objetivo: `{scan_result.get('ip', 'Desconocido')}`\nError: {scan_result['error']}",
                "color": 0xFF0000,
                "fields": []
            }
        
        summary = scan_result.get("summary", {})
        geo = scan_result.get("geolocation", {})
        ports = scan_result.get("open_ports", [])
        vulns = scan_result.get("critical_vulnerabilities", [])
        
        # Color basado en severidad
        if vulns:
            color = 0xFF0000  # Rojo - hay vulns críticas
        elif ports:
            color = 0xFFA500  # Naranja - puertos abiertos
        else:
            color = 0x00FF00  # Verde - limpio
        
        # Fields para el embed
        fields = [
            {
                "name": "🎯 IP Objetivo",
                "value": f"`{scan_result['ip']}`",
                "inline": True
            },
            {
                "name": "🌍 Ubicación",
                "value": f"{geo.get('city', 'N/A')}, {geo.get('country', 'N/A')}",
                "inline": True
            },
            {
                "name": "🏢 Organización",
                "value": geo.get("org", "N/A")[:50],
                "inline": True
            },
            {
                "name": f"🔓 Puertos Abiertos ({len(ports)})",
                "value": "\n".join([f"• **{p['port']}/{p['protocol']}** - {p['service']} {p['version']}".strip() for p in ports[:10]]) or "Ninguno",
                "inline": False
            }
        ]
        
        if vulns:
            fields.append({
                "name": f"🚨 Vulnerabilidades Críticas ({len(vulns)})",
                "value": "\n".join([f"• **{v['cve']}** (CVSS: {v['cvss']}) - {v['summary'][:80]}..." for v in vulns[:5]]) or "Ninguna",
                "inline": False
            })
        
        fields.append({
            "name": "📊 Resumen",
            "value": f"Puertos: {summary.get('total_ports', 0)} | Vulns Críticas: {summary.get('critical_vulns', 0)}",
            "inline": True
        })
        
        return {
            "title": "🔍 Perfil de Inteligencia Shodan",
            "description": f"Escaneo autónomo vía módulo Venice OSINT",
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"AURA Venice OSINT • {scan_result['timestamp']}"
            }
        }


def main():
    """CLI para testing directo."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Venice Shodan Scanner - OSINT Autónomo")
    parser.add_argument("target", help="IP o dominio a escanear")
    parser.add_argument("--api-key", help="Shodan API Key (opcional, usa env SHODAN_API_KEY)")
    parser.add_argument("--mode", choices=["host", "search", "vulns"], default="host",
                        help="Modo de escaneo")
    parser.add_argument("--query", help="Query para modo search (ej: 'apache country:PE')")
    parser.add_argument("--limit", type=int, default=10, help="Límite de resultados")
    parser.add_argument("--output", choices=["json", "discord"], default="json",
                        help="Formato de salida")
    parser.add_argument("--discord-embed", action="store_true",
                        help="Formatear para Discord embed")
    
    args = parser.parse_args()
    
    scanner = VeniceShodanScanner(api_key=args.api_key)
    
    if args.mode == "host":
        result = scanner.scan_host(args.target)
    elif args.mode == "search":
        if not args.query:
            args.query = args.target
        result = scanner.search(args.query, args.limit)
    elif args.mode == "vulns":
        result = scanner.get_vulnerabilities(args.target)
    else:
        result = {"error": "Modo no válido"}
    
    if args.discord_embed or args.output == "discord":
        output = scanner.format_for_discord_embed(result)
    else:
        output = result
    
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()