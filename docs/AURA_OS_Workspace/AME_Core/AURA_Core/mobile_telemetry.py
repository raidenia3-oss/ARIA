#!/usr/bin/env python3
"""
mobile_telemetry.py - Puente de telemetría y depuración móvil para AURA.
Este script establece una conexión ADB con un dispositivo móvil y monitorea logs de la aplicación AME.
"""

import os
import sys
import subprocess
import paramiko
import threading
import socket
import time
from typing import Optional, Dict, List

class MobileTelemetryBridge:
    def __init__(self, config: Dict):
        self.config = config
        self.adb_path = config.get("adb_path", "C:\\Users\\User\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe")
        self.app_package = config.get("app_package", "com.aura.mobile")
        self.ssh_host = config.get("ssh_host", "localhost")
        self.ssh_port = config.get("ssh_port", 22)
        self.ssh_username = config.get("ssh_username", "u0_a118")
        self.ssh_password = config.get("ssh_password", None)
        self.ssh_key_path = config.get("ssh_key_path", None)
        self.device_ip = None
        self.device_port = None
        self.adb_process = None
        self.ssh_client = None
        self.running = False

    def connect_adb(self, device_ip: str, device_port: int) -> bool:
        """Establece conexión ADB con el dispositivo móvil."""
        try:
            self.device_ip = device_ip
            self.device_port = device_port

            # Verificar conexión ADB
            result = subprocess.run(
                [self.adb_path, "connect", f"{device_ip}:{device_port}"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"[!] Error al conectar ADB: {result.stderr}")
                return False

            # Verificar si el dispositivo está conectado
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True
            )

            if f"{device_ip}:{device_port}" not in result.stdout:
                print(f"[!] Dispositivo {device_ip}:{device_port} no conectado correctamente")
                return False

            print(f"[+] Dispositivo conectado correctamente: {device_ip}:{device_port}")
            return True

        except Exception as e:
            print(f"[!] Error al conectar ADB: {str(e)}")
            return False

    def start_logcat(self) -> bool:
        """Inicia logcat con filtro para la aplicación AME."""
        if not self.device_ip or not self.device_port:
            print("[!] No hay dispositivo conectado")
            return False

        try:
            # Iniciar logcat en segundo plano con filtro para AME y Capacitor
            self.adb_process = subprocess.Popen(
                [
                    self.adb_path, "logcat",
                    "-s", f"{self.app_package}:V",
                    "-s", "Capacitor:V",
                    "-s", "WebView:E",
                    "-s", "System.err:E",
                    "--clear"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            print(f"[+] Logcat iniciado para {self.app_package}. Presione Ctrl+C para detener.")

            # Leer logs en tiempo real
            for line in self.adb_process.stdout:
                if self.running:
                    print(line.strip())

            return True
        except Exception as e:
            print(f"[!] Error al iniciar logcat: {str(e)}")
            return False

    def connect_ssh(self) -> bool:
        """Establece conexión SSH al dispositivo móvil."""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if self.ssh_key_path:
                private_key = paramiko.RSAKey.from_private_key_file(self.ssh_key_path)
                self.ssh_client.connect(
                    hostname=self.ssh_host,
                    port=self.ssh_port,
                    username=self.ssh_username,
                    pkey=private_key
                )
            else:
                self.ssh_client.connect(
                    hostname=self.ssh_host,
                    port=self.ssh_port,
                    username=self.ssh_username,
                    password=self.ssh_password
                )

            print(f"[+] Conexión SSH establecida correctamente al dispositivo")
            return True
        except Exception as e:
            print(f"[!] Error al conectar SSH: {str(e)}")
            return False

    def execute_ssh_command(self, command: str) -> Optional[str]:
        """Ejecuta un comando en el dispositivo móvil mediante SSH."""
        if not self.ssh_client:
            print("[!] No hay conexión SSH establecida")
            return None

        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode().strip()
            errors = stderr.read().decode().strip()

            if errors:
                print(f"[!] Error al ejecutar comando: {errors}")

            return output if output else None
        except Exception as e:
            print(f"[!] Error al ejecutar comando SSH: {str(e)}")
            return None

    def start_monitoring(self):
        """Inicia el monitoreo de logs y SSH."""
        self.running = True
        try:
            if not self.adb_process:
                self.start_logcat()

            # Mantener el script en ejecución
            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[!] Deteniendo el monitoreo...")
            self.running = False
        except Exception as e:
            print(f"[!] Error durante el monitoreo: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        """Detiene todos los procesos y cierra conexiones."""
        self.running = False

        if self.adb_process:
            self.adb_process.terminate()
            self.adb_process = None

        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

        # Desconectar dispositivo ADB
        if self.device_ip and self.device_port:
            try:
                subprocess.run(
                    [self.adb_path, "disconnect", f"{self.device_ip}:{self.device_port}"],
                    capture_output=True
                )
            except Exception as e:
                print(f"[!] Error al desconectar ADB: {str(e)}")

        print("[+] Todos los procesos detenidos")

def print_usage():
    """Imprime el uso del script."""
    print("""
    mobile_telemetry.py - Puente de telemetría móvil para AURA

    Uso:
        python mobile_telemetry.py --ip <IP_DISPOSITIVO> --port <PUERTO_ADB> [OPCIONES]

    Opciones:
        --ip <IP>              IP del dispositivo móvil (ej. 192.168.1.10)
        --port <PUERTO>        Puerto ADB del dispositivo (ej. 5555)
        --ssh-host <HOST>      Host SSH del dispositivo (ej. 192.168.1.10)
        --ssh-port <PUERTO>    Puerto SSH del dispositivo (ej. 8022)
        --ssh-user <USUARIO>  Usuario SSH (ej. u0_a118)
        --ssh-pass <CONTRASEÑA> Contraseña SSH (opcional)
        --ssh-key <RUTA>       Ruta al archivo de clave SSH privada (opcional)
        --app-package <PAQUETE> Paquete de la aplicación (ej. com.aura.mobile)
        --adb-path <RUTA>      Ruta al ejecutable ADB (ej. C:\\Users\\User\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe)
    """)

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Puente de telemetría móvil para AURA")
    parser.add_argument("--ip", required=True, help="IP del dispositivo móvil")
    parser.add_argument("--port", required=True, type=int, help="Puerto ADB del dispositivo")
    parser.add_argument("--ssh-host", default="localhost", help="Host SSH del dispositivo")
    parser.add_argument("--ssh-port", type=int, default=8022, help="Puerto SSH del dispositivo")
    parser.add_argument("--ssh-user", default="u0_a118", help="Usuario SSH")
    parser.add_argument("--ssh-pass", help="Contraseña SSH (opcional)")
    parser.add_argument("--ssh-key", help="Ruta al archivo de clave SSH privada (opcional)")
    parser.add_argument("--app-package", default="com.aura.mobile", help="Paquete de la aplicación")
    parser.add_argument("--adb-path", default="adb", help="Ruta al ejecutable ADB")

    args = parser.parse_args()

    config = {
        "adb_path": args.adb_path,
        "app_package": args.app_package,
        "ssh_host": args.ssh_host,
        "ssh_port": args.ssh_port,
        "ssh_username": args.ssh_user,
        "ssh_password": args.ssh_pass,
        "ssh_key_path": args.ssh_key
    }

    bridge = MobileTelemetryBridge(config)

    # Conectar ADB
    if not bridge.connect_adb(args.ip, args.port):
        print("[!] No se pudo conectar con ADB. Verifique la IP y el puerto.")
        sys.exit(1)

    # Intentar conectar SSH (opcional)
    try:
        if not bridge.connect_ssh():
            print("[!] No se pudo conectar con SSH. Continuando sin SSH...")
    except Exception as e:
        print(f"[!] Error al intentar conectar SSH: {str(e)}")

    # Iniciar monitoreo
    bridge.start_monitoring()

if __name__ == "__main__":
    main()