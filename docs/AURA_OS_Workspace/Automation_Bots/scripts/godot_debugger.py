#!/usr/bin/env python3
"""
godot_debugger.py - Depurador remoto para Godot 4.x
Autor: Cline
Licencia: MIT
"""

import socket
import json
import time
import subprocess
import os
import sys
from typing import List, Dict, Optional, Union
import threading
import queue
import select

class GodotDebugger:
    """
    Depurador remoto para Godot 4.x que se conecta al servidor de depuración de Godot.
    """

    def __init__(self, project_path="godot_game/", debug_port=6007):
        self.project_path = project_path
        self.debug_port = debug_port
        self.socket = None
        self.running = False
        self.message_queue = queue.Queue()
        self.receive_thread = None
        self.log_file = os.path.join("logs", "godot_debugger.log")
        self._setup_logging()

    def _setup_logging(self):
        """Configura el archivo de logs para el depurador."""
        os.makedirs("logs", exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write(f"📝 Iniciando Godot Debugger en {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    def connect(self, timeout=10) -> bool:
        """
        Conecta al servidor de depuración de Godot.

        Args:
            timeout: Tiempo máximo de espera para la conexión

        Returns:
            True si se conectó correctamente
        """
        if self.running:
            print("⚠️ El depurador ya está conectado")
            return True

        try:
            print(f"🔌 Conectando al servidor de depuración de Godot en puerto {self.debug_port}...")

            # Crear socket TCP
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)

            # Intentar conectar
            self.socket.connect(('localhost', self.debug_port))

            # Iniciar hilo para recibir mensajes
            self.receive_thread = threading.Thread(target=self._receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            self.running = True
            print("✅ Conectado al servidor de depuración de Godot")
            return True

        except socket.timeout:
            print("⏱️ Error: Tiempo de conexión agotado")
            return False
        except ConnectionRefusedError:
            print("❌ Error: No se pudo conectar al servidor de depuración")
            print("   Asegúrate de que Godot esté corriendo con --debug-server")
            return False
        except Exception as e:
            print(f"❌ Error al conectar: {e}")
            return False

    def disconnect(self):
        """Cierra la conexión con el servidor de depuración."""
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return

        try:
            print("🔌 Desconectando del servidor de depuración...")
            if self.socket:
                self.socket.close()
            self.running = False
            if self.receive_thread:
                self.receive_thread.join()
            print("✅ Desconectado correctamente")
        except Exception as e:
            print(f"❌ Error al desconectar: {e}")

    def _receive_messages(self):
        """Hilo para recibir mensajes del servidor de depuración."""
        while self.running:
            try:
                # Usar select para evitar bloqueos
                ready = select.select([self.socket], [], [], 1.0)

                if ready[0]:
                    data = self.socket.recv(4096)
                    if not data:
                        break

                    try:
                        message = json.loads(data.decode('utf-8'))
                        self.message_queue.put(message)
                        self._log_message("RECV", message)
                    except json.JSONDecodeError:
                        self._log_message("RAW", data.decode('utf-8'))

            except socket.timeout:
                continue
            except Exception as e:
                print(f"❌ Error al recibir mensajes: {e}")
                break

    def _log_message(self, direction: str, message: Union[Dict, str]):
        """Registra un mensaje en el archivo de logs."""
        timestamp = time.strftime('%H:%M:%S')
        with open(self.log_file, 'a') as f:
            if isinstance(message, dict):
                f.write(f"{timestamp} [{direction}] {json.dumps(message)}\n")
            else:
                f.write(f"{timestamp} [{direction}] {message}\n")

    def send_command(self, command: str, timeout=5) -> Optional[Dict]:
        """
        Envía un comando al servidor de depuración de Godot.

        Args:
            command: Comando a enviar (ej: "GameState.gain_xp(100)")
            timeout: Tiempo máximo de espera para la respuesta

        Returns:
            Respuesta del servidor o None si hubo error
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return None

        try:
            print(f"📤 Enviando comando: {command}")

            # Crear mensaje JSON
            message = {
                "type": "command",
                "command": command
            }

            # Enviar mensaje
            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "response":
                        return response
                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para la respuesta")
            return None

        except Exception as e:
            print(f"❌ Error al enviar comando: {e}")
            return None

    def get_errors(self, max_errors: int = 20) -> List[Dict]:
        """
        Obtiene los últimos errores del juego.

        Args:
            max_errors: Máximo número de errores a devolver

        Returns:
            Lista de errores con detalles
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return []

        try:
            print(f"🔍 Buscando últimos errores...")

            # Pedir errores al servidor
            message = {
                "type": "get_errors",
                "max_errors": max_errors
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "errors":
                        return response.get("errors", [])

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para obtener errores")
            return []

        except Exception as e:
            print(f"❌ Error al obtener errores: {e}")
            return []

    def get_scene_tree(self) -> Optional[Dict]:
        """
        Obtiene el árbol de escenas actual del juego.

        Returns:
            Representación JSON del árbol de escenas o None si hubo error
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return None

        try:
            print("🌳 Obteniendo árbol de escenas...")

            # Pedir árbol de escenas al servidor
            message = {
                "type": "get_scene_tree"
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "scene_tree":
                        return response.get("tree", {})

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para obtener árbol de escenas")
            return None

        except Exception as e:
            print(f"❌ Error al obtener árbol de escenas: {e}")
            return None

    def watch_variable(self, var_path: str, interval: float = 1.0) -> Optional[Dict]:
        """
        Monitorea una variable en tiempo real.

        Args:
            var_path: Ruta de la variable (ej: "GameState.hero_stats.level")
            interval: Intervalo de actualización en segundos

        Returns:
            Diccionario con información de monitoreo o None si hubo error
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return None

        try:
            print(f"👁️ Monitoreando variable: {var_path}")

            # Pedir monitoreo de variable
            message = {
                "type": "watch_variable",
                "var_path": var_path,
                "interval": interval
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta inicial
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "variable_watch":
                        return response

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para monitorear variable")
            return None

        except Exception as e:
            print(f"❌ Error al monitorear variable: {e}")
            return None

    def execute_gdscript(self, code: str) -> Dict:
        """
        Ejecuta GDScript arbitrario en el juego corriendo.

        Args:
            code: Código GDScript a ejecutar

        Returns:
            Diccionario con resultado de la ejecución
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return {"success": False, "output": "", "errors": []}

        try:
            print(f"💻 Ejecutando GDScript en el juego...")

            # Crear archivo temporal con el código
            temp_script = self._create_temp_script(code)

            # Pedir ejecución del script
            message = {
                "type": "execute_script",
                "script_path": temp_script
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            result = {"success": False, "output": "", "errors": []}

            while time.time() - start_time < 15:  # 15 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "script_result":
                        result = {
                            "success": response.get("success", False),
                            "output": response.get("output", ""),
                            "errors": response.get("errors", [])
                        }
                        break

                time.sleep(0.1)

            # Limpiar archivo temporal
            try:
                os.remove(temp_script)
            except:
                pass

            return result

        except Exception as e:
            print(f"❌ Error al ejecutar GDScript: {e}")
            return {"success": False, "output": "", "errors": [str(e)]}

    def _create_temp_script(self, code: str) -> str:
        """Crea un archivo temporal con el código GDScript."""
        temp_path = os.path.join("logs", "temp_script.gd")
        with open(temp_path, 'w') as f:
            f.write(code)
        return temp_path

    def start_debug_server(self) -> bool:
        """
        Inicia Godot con el servidor de depuración activado.

        Returns:
            True si se inició correctamente
        """
        try:
            print(f"🚀 Iniciando Godot con servidor de depuración en puerto {self.debug_port}...")

            # Verificar que Godot esté instalado
            godot_exec = self._find_godot_executable()
            if not godot_exec:
                print("❌ Error: No se encontró Godot instalado")
                return False

            # Iniciar Godot con el servidor de depuración
            process = subprocess.Popen(
                [godot_exec, "--path", self.project_path, "--debug-server", str(self.debug_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Esperar un momento para que el servidor inicie
            time.sleep(3)

            # Intentar conectar
            return self.connect()

        except Exception as e:
            print(f"❌ Error al iniciar servidor de depuración: {e}")
            return False

    def _find_godot_executable(self) -> Optional[str]:
        """Busca Godot en rutas comunes según el sistema operativo."""
        system = sys.platform.lower()

        # Rutas comunes según sistema operativo
        godot_paths = {
            'win32': [
                r"C:\Program Files\Godot\godot.exe",
                r"C:\Program Files (x86)\Godot\godot.exe",
                os.path.join(os.environ.get('GODOT_PATH', ''), 'godot.exe')
            ],
            'linux': [
                '/usr/bin/godot',
                '/usr/local/bin/godot',
                os.path.join(os.environ.get('HOME', ''), '.local/bin/godot')
            ],
            'darwin': [
                '/Applications/Godot.app/Contents/MacOS/Godot'
            ]
        }

        # Buscar en PATH
        if system in ['win32', 'linux', 'darwin']:
            for path in os.environ.get('PATH', '').split(os.pathsep):
                if system == 'win32':
                    exe = os.path.join(path, 'godot.exe')
                    if os.path.exists(exe):
                        return exe
                else:
                    if os.path.exists(os.path.join(path, 'godot')):
                        return os.path.join(path, 'godot')

        # Buscar en rutas específicas
        for path in godot_paths.get(system, []):
            if os.path.exists(path):
                return path

        return None

    def get_logs(self, lines: int = 50) -> List[str]:
        """
        Obtiene los últimos logs del juego.

        Args:
            lines: Número máximo de líneas a devolver

        Returns:
            Lista de líneas de log
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return []

        try:
            print(f"📝 Obteniendo últimos {lines} logs...")

            # Pedir logs al servidor
            message = {
                "type": "get_logs",
                "lines": lines
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "logs":
                        return response.get("logs", [])

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para obtener logs")
            return []

        except Exception as e:
            print(f"❌ Error al obtener logs: {e}")
            return []

    def get_variable_value(self, var_path: str) -> Optional[Dict]:
        """
        Obtiene el valor actual de una variable.

        Args:
            var_path: Ruta de la variable (ej: "GameState.hero_stats.level")

        Returns:
            Diccionario con el valor de la variable o None si hubo error
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return None

        try:
            print(f"🔍 Obteniendo valor de variable: {var_path}")

            # Pedir valor de variable
            message = {
                "type": "get_variable",
                "var_path": var_path
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "variable_value":
                        return response.get("value", {})

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para obtener valor de variable")
            return None

        except Exception as e:
            print(f"❌ Error al obtener valor de variable: {e}")
            return None

    def call_method(self, object_path: str, method_name: str, args: List = None) -> Optional[Dict]:
        """
        Llama a un método en un objeto del juego.

        Args:
            object_path: Ruta del objeto (ej: "/root/GameState")
            method_name: Nombre del método (ej: "gain_xp")
            args: Lista de argumentos para el método

        Returns:
            Diccionario con resultado de la llamada o None si hubo error
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return None

        try:
            print(f"📞 Llamando a método: {method_name} en {object_path}")

            # Pedir llamada al método
            message = {
                "type": "call_method",
                "object_path": object_path,
                "method_name": method_name,
                "args": args or []
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "method_result":
                        return response.get("result", {})

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para llamar al método")
            return None

        except Exception as e:
            print(f"❌ Error al llamar al método: {e}")
            return None

    def get_object_properties(self, object_path: str) -> Optional[Dict]:
        """
        Obtiene las propiedades de un objeto en el juego.

        Args:
            object_path: Ruta del objeto (ej: "/root/GameState")

        Returns:
            Diccionario con propiedades del objeto o None si hubo error
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return None

        try:
            print(f"📋 Obteniendo propiedades de objeto: {object_path}")

            # Pedir propiedades del objeto
            message = {
                "type": "get_object_properties",
                "object_path": object_path
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "object_properties":
                        return response.get("properties", {})

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para obtener propiedades")
            return None

        except Exception as e:
            print(f"❌ Error al obtener propiedades: {e}")
            return None

    def get_all_objects(self) -> Optional[Dict]:
        """
        Obtiene todos los objetos en la escena actual.

        Returns:
            Diccionario con todos los objetos o None si hubo error
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return None

        try:
            print("🌐 Obteniendo todos los objetos en la escena...")

            # Pedir todos los objetos
            message = {
                "type": "get_all_objects"
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar respuesta
            start_time = time.time()
            while time.time() - start_time < 15:  # 15 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "all_objects":
                        return response.get("objects", {})

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para obtener objetos")
            return None

        except Exception as e:
            print(f"❌ Error al obtener objetos: {e}")
            return None

    def pause_game(self) -> bool:
        """
        Pausa el juego en ejecución.

        Returns:
            True si se pausó correctamente
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return False

        try:
            print("⏸️ Pausando el juego...")

            # Pedir pausa al juego
            message = {
                "type": "pause_game"
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar confirmación
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "game_paused":
                        return True

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para pausar el juego")
            return False

        except Exception as e:
            print(f"❌ Error al pausar el juego: {e}")
            return False

    def resume_game(self) -> bool:
        """
        Reanuda el juego pausado.

        Returns:
            True si se reanudó correctamente
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return False

        try:
            print("▶️ Reanudando el juego...")

            # Pedir reanudación al juego
            message = {
                "type": "resume_game"
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar confirmación
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "game_resumed":
                        return True

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para reanudar el juego")
            return False

        except Exception as e:
            print(f"❌ Error al reanudar el juego: {e}")
            return False

    def step_frame(self) -> bool:
        """
        Ejecuta un solo frame del juego.

        Returns:
            True si se ejecutó correctamente
        """
        if not self.running:
            print("⚠️ El depurador no está conectado")
            return False

        try:
            print("🎮 Ejecutando un solo frame...")

            # Pedir ejecución de un frame
            message = {
                "type": "step_frame"
            }

            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self._log_message("SEND", message)

            # Esperar confirmación
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 segundos de espera
                if not self.message_queue.empty():
                    response = self.message_queue.get()
                    if response.get("type") == "frame_stepped":
                        return True

                time.sleep(0.1)

            print("⏱️ Error: Tiempo de espera agotado para ejecutar frame")
            return False

        except Exception as e:
            print(f"❌ Error al ejecutar frame: {e}")
            return False

if __name__ == "__main__":
    # Ejemplo de uso
    print("🚀 Iniciando Godot Debugger...")

    try:
        # Crear depurador
        debugger = GodotDebugger(project_path="godot_game/")

        # Iniciar servidor de depuración
        print("\n🔧 Iniciando servidor de depuración de Godot...")
        if debugger.start_debug_server():
            print("✅ Servidor de depuración iniciado correctamente")

            # Ejemplo: Obtener árbol de escenas
            print("\n🌳 Obteniendo árbol de escenas...")
            scene_tree = debugger.get_scene_tree()
            if scene_tree:
                print(f"📋 Árbol de escenas obtenido con {len(scene_tree)} nodos")

            # Ejemplo: Obtener errores
            print("\n🔍 Buscando errores...")
            errors = debugger.get_errors()
            if errors:
                print(f"⚠️ Encontrados {len(errors)} errores:")
                for i, error in enumerate(errors[:3]):  # Mostrar primeros 3 errores
                    print(f"  {i+1}. {error.get('message', 'Sin mensaje')}")
            else:
                print("✅ No hay errores")

            # Ejemplo: Obtener logs
            print("\n📝 Obteniendo últimos logs...")
            logs = debugger.get_logs(10)
            if logs:
                print(f"📋 Últimos {len(logs)} logs:")
                for log in logs:
                    print(f"  {log}")

            # Ejemplo: Ejecutar GDScript
            print("\n💻 Ejecutando GDScript de prueba...")
            result = debugger.execute_gdscript("""
print("Hola desde el depurador de Godot!")
var test_var = 10 + 20
print("Resultado: ", test_var)
return test_var
""")
            print(f"📋 Resultado de ejecución: {result}")

            # Ejemplo: Obtener valor de variable
            print("\n🔍 Obteniendo valor de variable...")
            var_value = debugger.get_variable_value("GameState/hero_stats/level")
            if var_value:
                print(f"📋 Valor de variable: {var_value}")

            # Ejemplo: Llamar a método
            print("\n📞 Llamando a método...")
            method_result = debugger.call_method("/root/GameState", "gain_xp", [100])
            if method_result:
                print(f"📋 Resultado del método: {method_result}")

        else:
            print("❌ No se pudo iniciar el servidor de depuración")

    except Exception as e:
        print(f"❌ Error en el depurador: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpiar
        debugger.disconnect()
        print("\n🛑 Godot Debugger detenido")