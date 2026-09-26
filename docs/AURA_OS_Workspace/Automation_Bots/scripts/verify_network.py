"""
Script de diagnostico de conectividad multi-cloud.
Verifica health de Railway, n8n, HF Space y endpoints locales.
Usa error_handler para capturar fallos sin interrumpir el flujo.
"""

import os, sys, json, time, socket, urllib.request, urllib.error

REPORT_FILE = "docs/network_health_report.md"

ENDPOINTS = {
    "HF Space": os.getenv("HF_SPACE_URL", "https://raiden456-slut.hf.space"),
    "Railway API": os.getenv("RAILWAY_API_URL", "http://localhost:8000"),
    "Vercel Frontend": os.getenv("VERCEL_FRONTEND_URL", "http://localhost:3000"),
    "n8n Render": "https://aura-n8n.onrender.com",
}

TIMEOUT = 10


class NetworkError(Exception):
    pass


class TimeoutError(NetworkError):
    pass


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except urllib.error.URLError as e:
            return False, f"Error de red: {e.reason}"
        except socket.timeout:
            return False, "Timeout excedido"
        except ConnectionRefusedError:
            return False, "Conexion rechazada"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    return wrapper


@error_handler
def check_http(url, path="/health"):
    target = url.rstrip("/") + path
    req = urllib.request.Request(target, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        status = resp.status
        body = resp.read().decode("utf-8", errors="ignore")[:200]
        return True, {"status": status, "body": body}


@error_handler
def check_dns(hostname):
    socket.getaddrinfo(hostname, 80)
    return True, "Resolucion DNS OK"


@error_handler
def check_tcp(host, port):
    s = socket.socket()
    s.settimeout(TIMEOUT)
    s.connect((host, port))
    s.close()
    return True, f"Puerto {port} abierto"


def extract_host(url):
    url = url.replace("http://", "").replace("https://", "")
    return url.split("/")[0].split(":")[0]


def run_all_checks():
    results = {}
    for name, url in ENDPOINTS.items():
        host = extract_host(url)
        print(f"  Verificando {name} ({url})...", end=" ")
        ok_dns, msg_dns = check_dns(host)
        ok_http, msg_http = check_http(url)
        results[name] = {
            "url": url,
            "dns": {"ok": ok_dns, "msg": msg_dns},
            "http": {"ok": ok_http, "msg": msg_http},
        }
        ok_char = "OK" if ok_http else "FAIL"
        print(f"  [{ok_char}] HTTP={ok_http} DNS={ok_dns}")
    return results


def generate_report(results):
    total = len(results)
    passed = sum(1 for r in results.values() if r["http"]["ok"])
    report = "# Network Health Report\n"
    report += "**Fecha:** " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n"
    report += "**Estado:** " + str(passed) + "/" + str(total) + " endpoints operativos\n"
    if passed == total:
        report += "**Resultado:** OK\n"
    else:
        report += "**Resultado:** ALERTA: " + str(total - passed) + " fallos\n"
    report += "\n## Endpoints Verificados\n\n"
    for name, data in results.items():
        ok = data["http"]["ok"]
        status = "OK" if ok else "FAIL"
        label = "OPERATIVO" if ok else "FALLO"
        http_msg = str(data["http"]["msg"])
        dns_msg = str(data["dns"]["msg"])
        report += "### " + status + " " + name + "\n"
        report += "- **URL:** `" + data["url"] + "`\n"
        report += "- **HTTP:** " + http_msg + "\n"
        report += "- **DNS:** " + dns_msg + "\n"
        report += "- **Estado:** " + label + "\n\n"
    return report


if __name__ == "__main__":
    print("=" * 50)
    print("VERIFICACION DE RED MULTI-CLOUD")
    print("=" * 50)
    os.makedirs("docs", exist_ok=True)
    results = run_all_checks()
    report = generate_report(results)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print("\nReporte generado: " + REPORT_FILE)
