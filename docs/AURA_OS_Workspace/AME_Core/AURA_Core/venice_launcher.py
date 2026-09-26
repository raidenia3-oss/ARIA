#!/usr/bin/env python3
"""
venice_launcher.py - Launcher para módulos Venice en dispositivos móviles (Termux).
Este script recibe órdenes de AURA, ejecuta módulos en el directorio /sdcard/venice_modules/
y devuelve la salida (stdout/stderr) a la PC.

Características:
- Agnóstico a los módulos: No importa qué módulo se ejecute.
- Captura stdout y stderr por separado.
- Manejo de errores y tiempo de ejecución.
- Soporte para parámetros de entrada.
"""

import os
import sys
import subprocess
import json
import logging
import signal
import time
from typing import Dict, Optional, Tuple

class VeniceLauncher:
    def __init__(self, config: Dict):
        self.config = config
        self.modules_dir = config.get("modules_dir", "/sdcard/venice_modules/")
        self.timeout = config.get("timeout", 30)  # segundos
        self.max_memory = config.get("max_memory", 256)  # MB
        self.logger = self._setup_logging()
        self._ensure_modules_dir_exists()

    def _setup_logging(self):
        """Configura el logging para el launcher."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/sdcard/venice_launcher.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger("VeniceLauncher")

    def _ensure_modules_dir_exists(self):
        """Asegura que el directorio de módulos exista."""
        try:
            if not os.path.exists(self.modules_dir):
                os.makedirs(self.modules_dir)
                self.logger.info(f"Directorio de módulos creado: {self.modules_dir}")
        except Exception as e:
            self.logger.error(f"Error al crear directorio de módulos: {str(e)}")
            raise

    def _validate_module_path(self, module_path: str) -> bool:
        """Valida que el módulo esté dentro del directorio de módulos."""
        if not os.path.isabs(module_path):
            module_path = os.path.join(self.modules_dir, module_path)

        # Verificar que el módulo esté dentro del directorio de módulos
        real_path = os.path.realpath(module_path)
        real_modules_dir = os.path.realpath(self.modules_dir)

        if not real_path.startswith(real_modules_dir):
            self.logger.error(f"Intento de acceso fuera del directorio de módulos: {module_path}")
            return False

        return True

    def _execute_module(self, module_path: str, args: list, timeout: int) -> Tuple[str, str, int]:
        """
        Ejecuta un módulo y captura stdout, stderr y código de retorno.
        """
        try:
            if not self._validate_module_path(module_path):
                return "", "Error: Ruta de módulo no válida", 1

            # Construir el comando completo
            command = [sys.executable, module_path] + args

            # Configurar el proceso con límites de tiempo y memoria
            start_time = time.time()
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Permite matar el grupo de procesos
            )

            # Esperar por el proceso con timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Matar el proceso si excede el tiempo
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                stdout, stderr = process.communicate()
                return stdout.decode('utf-8', errors='replace'), \
                       f"Error: Tiempo de ejecución excedido ({timeout} segundos)\n{stderr.decode('utf-8', errors='replace')}", \
                       -1

            return stdout.decode('utf-8', errors='replace'), \
                   stderr.decode('utf-8', errors='replace'), \
                   process.returncode

        except Exception as e:
            self.logger.error(f"Error al ejecutar módulo {module_path}: {str(e)}")
            return "", f"Error interno: {str(e)}", 1

    def _parse_command(self, command_str: str) -> Dict:
        """
        Parsea una cadena de comando en un diccionario con módulo, argumentos y parámetros.
        Ejemplo de entrada: "module_name arg1 arg2 --param value"
        """
        try:
            # Dividir en partes: módulo y argumentos
            parts = command_str.split(maxsplit=1)
            if len(parts) < 1:
                raise ValueError("Comando vacío")

            module_path = parts[0]
            args = parts[1].split() if len(parts) > 1 else []

            # Verificar que el módulo exista
            if not os.path.isfile(module_path):
                module_path = os.path.join(self.modules_dir, module_path)
                if not os.path.isfile(module_path):
                    raise FileNotFoundError(f"Módulo no encontrado: {module_path}")

            return {
                "module_path": module_path,
                "args": args,
                "timeout": self.timeout,
                "max_memory": self.max_memory
            }

        except Exception as e:
            self.logger.error(f"Error al parsear comando: {str(e)}")
            raise ValueError(f"Formato de comando inválido: {str(e)}")

    def execute(self, command_str: str) -> Dict:
        """
        Ejecuta un comando y devuelve el resultado en formato JSON.
        """
        try:
            # Parsear el comando
            command = self._parse_command(command_str)

            # Ejecutar el módulo
            stdout, stderr, returncode = self._execute_module(
                command["module_path"],
                command["args"],
                command["timeout"]
            )

            # Construir la respuesta
            response = {
                "status": "success",
                "module": os.path.basename(command["module_path"]),
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "execution_time": time.time() - time.time()  # Placeholder, se calcula en el llamado real
            }

            return response

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def handle_stdin(self):
        """
        Lee comandos desde stdin (para uso en tuberías o interacción directa).
        """
        try:
            while True:
                # Leer línea desde stdin
                command_str = sys.stdin.readline().strip()

                if not command_str:
                    break  # Fin de entrada

                # Ejecutar el comando
                result = self.execute(command_str)

                # Imprimir resultado en stdout (formato JSON)
                print(json.dumps(result))

        except KeyboardInterrupt:
            self.logger.info("Launcher detenido por el usuario.")
        except Exception as e:
            self.logger.error(f"Error en el bucle principal: {str(e)}")
            print(json.dumps({
                "status": "error",
                "message": f"Error interno: {str(e)}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }))
        finally:
            self.logger.info("Finalizando Venice Launcher.")

def main():
    """Punto de entrada principal del Venice Launcher."""
    config = {
        "modules_dir": "/sdcard/venice_modules/",
        "timeout": 30,
        "max_memory": 256
    }

    launcher = VeniceLauncher(config)

    # Si se ejecuta directamente (no como módulo importado)
    if __name__ == "__main__":
        # Leer comando desde stdin (para uso en tuberías)
        launcher.handle_stdin()

def run_from_command_line(args: list):
    """
    Función para ejecutar el launcher desde la línea de comandos con argumentos.
    Útil para pruebas y depuración.
    """
    config = {
        "modules_dir": "/sdcard/venice_modules/",
        "timeout": 30,
        "max_memory": 256
    }

    launcher = VeniceLauncher(config)

    if len(args) < 2:
        print("Uso: python venice_launcher.py <módulo> [args...]")
        sys.exit(1)

    # Construir el comando como si viniera de stdin
    command_str = " ".join(args[1:])
    result = launcher.execute(args[1])

    # Imprimir resultado en formato JSON
    print(json.dumps(result))

if __name__ == "__main__":
    # Si se ejecuta con argumentos de línea de comandos, usarlos directamente
    if len(sys.argv) > 1:
        run_from_command_line(sys.argv)
    else:
        main()