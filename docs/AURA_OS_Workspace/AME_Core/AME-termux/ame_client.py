"""
AME Client — ame_client.py
Servidor HTTP mínimo para servir el dashboard.html al móvil (LG Q60).
Puerto: 8080
No requiere Flask — usa http.server nativo de Python para máxima ligereza.
"""
import http.server
import socketserver
import os
import sys
import json

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Health log path (monitoreo) ──
HEALTH_LOG = os.path.join(BASE_DIR, '..', 'AURA_Core', 'system_health.log')


class AuraHandler(http.server.SimpleHTTPRequestHandler):
    """Handler personalizado con CORS para el móvil."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        # ── Health-log endpoint ──
        if self.path == '/api/health-log':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                if os.path.exists(HEALTH_LOG):
                    with open(HEALTH_LOG, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    entries = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
                    self.wfile.write(json.dumps({"entries": entries[-30:]}).encode())
                else:
                    self.wfile.write(json.dumps({"entries": []}).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # ── Proxy /api/status hacia servidor AME (puerto 5000) ──
        if self.path == '/api/status':
            import urllib.request
            try:
                resp = urllib.request.urlopen('http://localhost:5000/api/status', timeout=5)
                data = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "master_online": False,
                    "bots": {},
                    "ram_free_gb": 0,
                    "uptime": "N/A",
                    "system_health": "proxy_error",
                    "error": str(e)
                }).encode())
            return

        # ── Default: servir archivos estáticos ──
        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """Log silencioso pero con timestamp."""
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        sys.stderr.write(f"[AME {ts}] {args[0]} {args[1]} {args[2]}\n")


def main():
    print("\n" + "="*45)
    print("  📱 AME Client — Mobile Dashboard")
    print(f"  🌐 http://0.0.0.0:{PORT}")
    print(f"  📁 Sirviendo: {BASE_DIR}")
    print("  🔄 Proxy /api/status → localhost:5000")
    print("="*45 + "\n")

    with socketserver.TCPServer(("0.0.0.0", PORT), AuraHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n⏹️  AME Client detenido.")
            httpd.server_close()


if __name__ == "__main__":
    main()