import subprocess
import xml.etree.ElementTree as ET
import json
import os
import re
from datetime import datetime
from pathlib import Path


class NodNmapAdvanced:
    """
    Wrapper avanzado de Nmap para auditorias de red en laboratorio controlado.
    Orquesta escaneos con NSE, evasión de IDS y exportación multi-formato.
    """

    OUTPUT_DIR = Path("AURA_Core/nodes/nmap_reports")
    NMAP_BINARY = "nmap"

    def __init__(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._verify_nmap()

    def _verify_nmap(self):
        """Verificar que Nmap está instalado y accesible."""
        try:
            result = subprocess.run(
                [self.NMAP_BINARY, "--version"],
                capture_output=True, text=True, timeout=10
            )
            version = result.stdout.strip().split("\n")[0]
            print(f"[NMAP] {version}")
        except FileNotFoundError:
            raise RuntimeError("Nmap no encontrado. Instalar: nmap.org/download.html")
        except Exception as e:
            raise RuntimeError(f"Error verificando Nmap: {e}")

    def _run_nmap(self, args: list[str], timeout: int = 600) -> tuple[str, int]:
        """Ejecutar Nmap con los argumentos dados y capturar salida XML."""
        cmd = [self.NMAP_BINARY] + args
        print(f"[NMAP] Ejecutando: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", -1
        except Exception as e:
            return str(e), -2

    def deep_recon(self, target: str) -> dict:
        """
        Escaneo de reconocimiento profundo:
        -sV: deteccion de versiones
        -O: deteccion de SO
        -p-: todos los puertos
        -T4: velocidad agresiva
        -A: deteccion completa (OS, version, scripts, traceroute)
        """
        scan_id = f"deep_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        xml_output = str(self.OUTPUT_DIR / f"{scan_id}.xml")

        args = [
            "-sV", "-O", "-A", "-T4", "-p-",
            "--open",
            "-oX", xml_output,
            target
        ]

        output, rc = self._run_nmap(args, timeout=1800)
        if rc != 0 and rc != -1:
            return {"scan_id": scan_id, "status": "failure",
                    "error": f"Nmap fallo con codigo {rc}", "raw_output": output}

        return self._parse_xml(scan_id, xml_output)

    def scan_vulnerabilities(self, target: str,
                              script_category: str = "vuln",
                              specific_script: str = None) -> dict:
        """
        Escaneo con scripts NSE por categoria.
        script_category: vuln, exploit, auth, safe, discovery
        specific_script: nombre exacto de script (ej: smb-brute)
        """
        scan_id = f"vuln_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        xml_output = str(self.OUTPUT_DIR / f"{scan_id}.xml")

        if specific_script:
            script_arg = f"--script={specific_script}"
        else:
            script_arg = f"--script={script_category}"

        args = [
            "-sV", "-T4", "--open",
            script_arg,
            "-oX", xml_output,
            target
        ]

        output, rc = self._run_nmap(args, timeout=900)
        if rc != 0 and rc != -1:
            return {"scan_id": scan_id, "status": "failure",
                    "error": f"Nmap fallo con codigo {rc}"}

        result = self._parse_xml(scan_id, xml_output)
        # Filtrar vulnerabilidades criticas/alta severidad
        if "vulnerabilities" in result:
            result["vulnerabilities"] = [
                v for v in result["vulnerabilities"]
                if v.get("severity", "").lower() in ["critical", "high", "high-risk"]
                or "VULNERABLE" in str(v.get("output", "")).upper()
            ]
        return result

    def stealth_scan(self, target: str, use_evasion: bool = True) -> dict:
        """
        Escaneo sigiloso con evasión de IDS/IPS.
        -f: fragmentacion de paquetes
        -sN: escaneo nulo
        -D RND:10: decos aleatorios
        --scan-delay: retardo entre paquetes
        -T2: velocidad lenta para evadir deteccion
        """
        scan_id = f"stealth_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        xml_output = str(self.OUTPUT_DIR / f"{scan_id}.xml")

        args = ["-sS", "-T2", "--open", "-oX", xml_output]

        if use_evasion:
            args.extend([
                "-f",                    # Fragmentacion de paquetes
                "-D", "RND:10",          # 10 decos aleatorios
                "--scan-delay", "500ms",  # Retardo entre paquetes
                "--source-port", "53",    # Puerto fuente DNS
            ])
        else:
            args.append("-T4")

        args.append(target)
        output, rc = self._run_nmap(args, timeout=1200)

        result = self._parse_xml(scan_id, xml_output)
        result["evasion_used"] = use_evasion
        return result

    def _parse_xml(self, scan_id: str, xml_path: str) -> dict:
        """Parsear salida XML de Nmap a diccionario estructurado."""
        result = {
            "scan_id": scan_id,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "open_ports": [],
            "services": [],
            "vulnerabilities": [],
            "os_detection": [],
            "hosts": [],
        }

        if not os.path.exists(xml_path):
            result["status"] = "failure"
            result["error"] = "Archivo XML no generado"
            return result

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            for host in root.findall(".//host"):
                host_info = {}
                # IP del host
                addr = host.find("address[@addrtype='ipv4']")
                if addr is not None:
                    host_info["ip"] = addr.get("addr")

                # Estado del host
                status = host.find("status")
                if status is not None:
                    host_info["state"] = status.get("state")

                # Puertos abiertos
                for port in host.findall(".//port"):
                    port_id = port.get("portid")
                    protocol = port.get("protocol")

                    state_el = port.find("state")
                    state = state_el.get("state") if state_el is not None else "unknown"

                    if state == "open":
                        result["open_ports"].append({
                            "port": int(port_id),
                            "protocol": protocol,
                            "state": state,
                        })

                    # Servicio detectado
                    service = port.find("service")
                    if service is not None:
                        svc_info = {
                            "port": int(port_id),
                            "service": service.get("name", "unknown"),
                            "product": service.get("product", ""),
                            "version": service.get("version", ""),
                            "extra": service.get("extrainfo", ""),
                        }
                        result["services"].append(svc_info)

                    # Scripts NSE ejecutados
                    for script in port.findall("script"):
                        script_id = script.get("id", "")
                        script_output = script.get("output", "")
                        if "vuln" in script_id.lower() or "VULNERABLE" in script_output.upper():
                            result["vulnerabilities"].append({
                                "port": int(port_id),
                                "script": script_id,
                                "output": script_output[:500],
                                "severity": self._classify_severity(script_output),
                            })

                # Deteccion de SO
                os_matches = host.findall(".//osmatch")
                for os_match in os_matches:
                    result["os_detection"].append({
                        "name": os_match.get("name", ""),
                        "accuracy": os_match.get("accuracy", ""),
                    })

                result["hosts"].append(host_info)

        except ET.ParseError as e:
            result["status"] = "failure"
            result["error"] = f"Error parseando XML: {e}"
        except Exception as e:
            result["status"] = "failure"
            result["error"] = f"Error inesperado: {e}"

        return result

    def _classify_severity(self, output: str) -> str:
        """Clasificar severidad basado en el output del script."""
        output_lower = output.lower()
        if "critical" in output_lower or "VULNERABLE" in output.upper():
            return "critical"
        elif "high" in output_lower:
            return "high"
        elif "medium" in output_lower:
            return "medium"
        elif "low" in output_lower:
            return "low"
        return "info"

    def export_results(self, scan_id: str, fmt: str = "json") -> str:
        """
        Exportar resultados en formato json, xml, o grepable.
        Retorna la ruta del archivo exportado.
        """
        xml_source = self.OUTPUT_DIR / f"{scan_id}.xml"
        if not xml_source.exists():
            return f"Error: scan_id {scan_id} no encontrado"

        if fmt == "json":
            result = self._parse_xml(scan_id, str(xml_source))
            out_path = self.OUTPUT_DIR / f"{scan_id}.json"
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            return str(out_path)

        elif fmt == "grepable":
            grepable_path = self.OUTPUT_DIR / f"{scan_id}.gnmap"
            if grepable_path.exists():
                return str(grepable_path)
            return f"Error: archivo grepable no generado por Nmap"

        elif fmt == "xml":
            return str(xml_source)

        elif fmt == "html":
            html_path = self.OUTPUT_DIR / f"{scan_id}.html"
            try:
                # Convertir XML a HTML usando xsltproc si esta disponible
                xslt_proc = Path("AURA_Core/recon/nmap_xml2html.xsl")
                if xslt_proc.exists():
                    subprocess.run(
                        ["xsltproc", str(xslt_proc), str(xml_source), "-o", str(html_path)],
                        capture_output=True, timeout=30
                    )
                else:
                    # Fallback: generar HTML basico desde JSON
                    data = self._parse_xml(scan_id, str(xml_source))
                    html_content = self._generate_html_report(data)
                    with open(html_path, "w") as f:
                        f.write(html_content)
                return str(html_path)
            except Exception as e:
                return f"Error generando HTML: {e}"

        return f"Formato no soportado: {fmt}"

    def _generate_html_report(self, data: dict) -> str:
        """Generar reporte HTML basico desde datos parseados."""
        html = f"""<!DOCTYPE html>
<html><head><title>Nmap Report - {data.get('scan_id', '')}</title>
<style>
body {{ font-family: monospace; background: #1a1a2e; color: #0f0; padding: 20px; }}
h1 {{ color: #00ff41; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #333; padding: 8px; text-align: left; }}
th {{ background: #16213e; color: #00ff41; }}
.vuln-critical {{ color: #ff0000; font-weight: bold; }}
.vuln-high {{ color: #ff6600; }}
.open {{ color: #00ff41; }}
</style></head><body>
<h1>AURA Nmap Report</h1>
<p>Scan ID: {data.get('scan_id', 'N/A')}</p>
<p>Timestamp: {data.get('timestamp', 'N/A')}</p>
<h2>Hosts ({len(data.get('hosts', []))})</h2>
<table><tr><th>IP</th><th>State</th></tr>"""
        for h in data.get("hosts", []):
            html += f"<tr><td>{h.get('ip','')}</td><td>{h.get('state','')}</td></tr>"
        html += "</table>"

        html += f"<h2>Open Ports ({len(data.get('open_ports', []))})</h2>"
        html += "<table><tr><th>Port</th><th>Protocol</th></tr>"
        for p in data.get("open_ports", []):
            html += f"<tr class='open'><td>{p['port']}</td><td>{p['protocol']}</td></tr>"
        html += "</table>"

        html += f"<h2>Services ({len(data.get('services', []))})</h2>"
        html += "<table><tr><th>Port</th><th>Service</th><th>Product</th><th>Version</th></tr>"
        for s in data.get("services", []):
            html += f"<tr><td>{s['port']}</td><td>{s['service']}</td><td>{s['product']}</td><td>{s['version']}</td></tr>"
        html += "</table>"

        html += f"<h2>Vulnerabilities ({len(data.get('vulnerabilities', []))})</h2>"
        html += "<table><tr><th>Port</th><th>Script</th><th>Severity</th><th>Output</th></tr>"
        for v in data.get("vulnerabilities", []):
            sev_class = f"vuln-{v.get('severity', 'info')}"
            html += f"<tr class='{sev_class}'><td>{v.get('port','')}</td><td>{v.get('script','')}</td><td>{v.get('severity','')}</td><td>{v.get('output','')[:200]}</td></tr>"
        html += "</table></body></html>"
        return html

    def execute(self, input_data: dict) -> dict:
        """
        Funcion principal de orquestacion.
        input_data: {"target":"IP", "scan_type":"deep", "use_evasion":false, "nse_scripts":["vuln"]}
        """
        target = input_data.get("target")
        scan_type = input_data.get("scan_type", "deep")
        use_evasion = input_data.get("use_evasion", False)
        nse_scripts = input_data.get("nse_scripts", [])

        if not target:
            return {"status": "failure", "error": "Target no especificado"}

        # Seleccionar tipo de escaneo
        if scan_type == "deep":
            result = self.deep_recon(target)
        elif scan_type == "stealth":
            result = self.stealth_scan(target, use_evasion=use_evasion)
        elif scan_type == "vuln":
            script = nse_scripts[0] if nse_scripts else "vuln"
            result = self.scan_vulnerabilities(target, script_category=script)
        else:
            # Escaneo basico por defecto
            result = self.deep_recon(target)

        # Ejecutar scripts NSE adicionales si se solicitaron
        if nse_scripts and scan_type not in ["vuln"]:
            for script in nse_scripts:
                extra = self.scan_vulnerabilities(target, specific_script=script)
                if "vulnerabilities" in extra:
                    result.setdefault("vulnerabilities", []).extend(
                        extra["vulnerabilities"]
                    )

        # Exportar como JSON por defecto
        if result.get("status") == "success":
            json_path = self.export_results(result["scan_id"], "json")
            result["report_json"] = json_path

        return result


# Instancia global para uso desde Discord bot o AURA
nmap_advanced = NodNmapAdvanced()


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    scan_type = sys.argv[2] if len(sys.argv) > 2 else "deep"

    input_data = {
        "target": target,
        "scan_type": scan_type,
        "use_evasion": scan_type == "stealth",
        "nse_scripts": ["vuln"],
    }

    result = nmap_advanced.execute(input_data)
    print(json.dumps(result, indent=2, default=str))