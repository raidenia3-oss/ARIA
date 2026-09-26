"""
Servidor estático para AURA que permite el acceso desde la red local.
Este servidor debe estar disponible para dispositivos en la misma red WiFi.
"""

import os
import http.server
import socketserver
from http import HTTPStatus

# Configuración del servidor
PORT = 8000
DIRECTORY = os.path.join(os.path.dirname(__file__), "..", "dist")

class AuraStaticHandler(http.server.SimpleHTTPRequestHandler):
    """Maneja solicitudes HTTP para servir archivos estáticos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        """Desactiva el logging por defecto para evitar mensajes en consola."""
        return

    def do_GET(self):
        """Maneja solicitudes GET."""
        try:
            # Verificar si la ruta es para descargar el APK
            if self.path == '/descargar-ame':
                apk_path = os.path.join(DIRECTORY, "AME_Client_v1.apk")
                if os.path.exists(apk_path):
                    self.send_head(200, {'Content-Type': 'application/vnd.android.package-archive'})
                    with open(apk_path, 'rb') as file:
                        self.wfile.write(file.read())
                    return

            # Para cualquier otra ruta, servir el archivo estático
            super().do_GET()
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))

def run_server():
    """Inicia el servidor en 0.0.0.0 para permitir acceso desde la red local."""
    print(f"🚀 Servidor estático iniciado en http://0.0.0.0:{PORT}")
    print(f"📂 Serviendo archivos desde: {DIRECTORY}")
    print(f"🔓 Accesible desde cualquier dispositivo en la red local (ej: http://192.168.3.10:{PORT})")

    # Configurar el servidor para escuchar en todas las interfaces de red
    with socketserver.TCPServer(("0.0.0.0", PORT), AuraStaticHandler) as httpd:
        try:
            print(f"🔌 Esperando conexiones en el puerto {PORT}...")
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Servidor detenido por el usuario")
        except Exception as e:
            print(f"❌ Error al iniciar el servidor: {e}")

if __name__ == "__main__":
    # Verificar que el directorio exista
    if not os.path.exists(DIRECTORY):
        print(f"❌ Error: El directorio {DIRECTORY} no existe")
        print("🔧 Por favor, asegúrate de que el APK esté compilado y en la carpeta dist")
        exit(1)

    # Verificar que el APK exista
    apk_path = os.path.join(DIRECTORY, "AME_Client_v1.apk")
    if not os.path.exists(apk_path):
        print(f"❌ Error: El archivo {apk_path} no existe")
        print("🔧 Por favor, compila el APK antes de iniciar el servidor")
        exit(1)

    run_server()