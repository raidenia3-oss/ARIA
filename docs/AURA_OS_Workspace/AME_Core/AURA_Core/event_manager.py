#!/usr/bin/env python3
"""
event_manager.py - Gestor de eventos autónomos para el sistema AURA.
Este módulo permite definir reglas de tipo 'TRIGGER -> ACTION' y las evalúa periódicamente
para ejecutar acciones basadas en los datos de telemetría de los nodos móviles.
"""

import os
import json
import time
import logging
from typing import Any, Dict, List, Optional
from AURA_Core.security.input_validator import InputValidator, SecurityValidationError
from AURA_Core.modules.iot_manager import IoTManager
from AURA_Core.chronos import Chronos
from AURA_Core.hud.emote_engine import AvatarState, get_emote_engine
from AURA_Core.hud.canvas_generator import attach_ws as attach_canvas_ws
from AURA_Core.automation.n8n_bridge import n8n_bridge
import subprocess
import platform
import sys
from datetime import datetime


class EventManager:
    def __init__(self, config: Dict):
        self.config = config
        self.rules_file = config.get("rules_file", "rules.json")
        self.check_interval = config.get("check_interval", 30)  # segundos
        self.telemetry_file = config.get("telemetry_file", "telemetry_history.json")
        self.logger = self._setup_logging()
        self.rules = self._load_rules()
        self.last_checked = 0
        self.iot = IoTManager(simulate=True)
        self.chronos = Chronos(simulate=True)
        self.chronos.register_ws(self)
        self.emote = get_emote_engine()
        self.emote.attach_ws(self._broadcast_ws)
        attach_canvas_ws(self._broadcast_ws)
        self._last_canvas_update = 0
        self._voice_stream = None
        self._voice_active = False

    def _setup_logging(self):
        """Configura el logging para el EventManager."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("event_manager.log"), logging.StreamHandler()],
        )
        return logging.getLogger("EventManager")

    def _load_rules(self) -> List[Dict]:
        """Carga las reglas desde el archivo JSON."""
        try:
            if os.path.exists(self.rules_file):
                with open(self.rules_file, "r") as f:
                    rules = json.load(f)
                    self.logger.info(f"Cargadas {len(rules)} reglas.")
                    return rules
            else:
                self.logger.warning(
                    f"Archivo de reglas no encontrado: {self.rules_file}. Creando uno por defecto."
                )
                return self._get_default_rules()
        except Exception as e:
            self.logger.error(f"Error al cargar las reglas: {str(e)}")
            return self._get_default_rules()

    def _get_default_rules(self) -> List[Dict]:
        """Devuelve un conjunto de reglas por defecto."""
        return [
            {
                "id": "low_battery_alert",
                "description": "Alerta cuando la batería de un nodo móvil está por debajo del 20%",
                "trigger": {
                    "device_id": "*",  # Aplica a todos los dispositivos
                    "condition": "battery_level < 20",
                    "field": "battery_level",
                },
                "actions": [
                    {
                        "type": "desktop_notification",
                        "message": "¡Advertencia! Batería baja en el nodo {{device_id}} ({{battery_level}}%).",
                        "title": "Batería Crítica",
                    },
                    {"type": "stop_high_consumption_workers", "device_id": "{{device_id}}"},
                ],
            },
            {
                "id": "high_cpu_usage",
                "description": "Alerta cuando el uso de CPU supera el 90%",
                "trigger": {"device_id": "*", "condition": "cpu_usage > 90", "field": "cpu_usage"},
                "actions": [
                    {
                        "type": "desktop_notification",
                        "message": "¡Advertencia! Alto uso de CPU en el nodo {{device_id}} ({{cpu_usage}}%).",
                        "title": "CPU Sobrecargada",
                    }
                ],
            },
            {
                "id": "high_temperature",
                "description": "Alerta cuando la temperatura supera los 50°C",
                "trigger": {
                    "device_id": "*",
                    "condition": "temperature > 50",
                    "field": "temperature",
                },
                "actions": [
                    {
                        "type": "desktop_notification",
                        "message": "¡Advertencia! Temperatura alta en el nodo {{device_id}} ({{temperature}}°C).",
                        "title": "Sobrecalentamiento",
                    }
                ],
            },
            {
                "id": "connection_lost",
                "description": "Alerta cuando un nodo pierde conexión",
                "trigger": {
                    "device_id": "*",
                    "condition": "connection_status == 'inactive'",
                    "field": "connection_status",
                },
                "actions": [
                    {
                        "type": "desktop_notification",
                        "message": "¡Advertencia! Conexión perdida con el nodo {{device_id}}.",
                        "title": "Conexión Perdida",
                    }
                ],
            },
            {
                "id": "voice_advanced_mining_mode",
                "description": "Comando de voz: Modo Minería Avanzado",
                "trigger": {"device_id": "*", "condition": "True", "field": "voice_command"},
                "actions": [
                    {
                        "type": "command_voice",
                        "text": "Modo Minería Avanzado",
                        "room_id": "game_room",
                    },
                    {
                        "type": "desktop_notification",
                        "message": "Modo Minería Avanzado activado.",
                        "title": "Comando de Voz",
                    },
                ],
            },
        ]

    def _save_rules(self):
        """Guarda las reglas en el archivo JSON."""
        try:
            with open(self.rules_file, "w") as f:
                json.dump(self.rules, f, indent=2)
            self.logger.info("Reglas guardadas correctamente.")
        except Exception as e:
            self.logger.error(f"Error al guardar las reglas: {str(e)}")

    def add_rule(self, rule: Dict):
        """Agrega una nueva regla al sistema."""
        try:
            rule_id = rule.get("id")
            if not rule_id:
                raise ValueError("La regla debe tener un ID único.")

            # Verificar si la regla ya existe
            for existing_rule in self.rules:
                if existing_rule.get("id") == rule_id:
                    raise ValueError(f"Ya existe una regla con el ID: {rule_id}")

            self.rules.append(rule)
            self._save_rules()
            self.logger.info(f"Regla agregada: {rule_id}")
        except Exception as e:
            self.logger.error(f"Error al agregar regla: {str(e)}")
            raise

    def update_rule(self, rule_id: str, updated_rule: Dict):
        """Actualiza una regla existente."""
        try:
            for i, rule in enumerate(self.rules):
                if rule.get("id") == rule_id:
                    self.rules[i] = updated_rule
                    self._save_rules()
                    self.logger.info(f"Regla actualizada: {rule_id}")
                    return
            raise ValueError(f"No se encontró una regla con el ID: {rule_id}")
        except Exception as e:
            self.logger.error(f"Error al actualizar regla: {str(e)}")
            raise

    def delete_rule(self, rule_id: str):
        """Elimina una regla existente."""
        try:
            initial_count = len(self.rules)
            self.rules = [rule for rule in self.rules if rule.get("id") != rule_id]
            if len(self.rules) < initial_count:
                self._save_rules()
                self.logger.info(f"Regla eliminada: {rule_id}")
            else:
                raise ValueError(f"No se encontró una regla con el ID: {rule_id}")
        except Exception as e:
            self.logger.error(f"Error al eliminar regla: {str(e)}")
            raise

    def _load_telemetry_data(self) -> Dict:
        """Carga los datos de telemetría desde el archivo JSON."""
        try:
            if os.path.exists(self.telemetry_file):
                with open(self.telemetry_file, "r") as f:
                    return json.load(f)
            else:
                self.logger.warning(f"Archivo de telemetría no encontrado: {self.telemetry_file}")
                return {}
        except Exception as e:
            self.logger.error(f"Error al cargar datos de telemetría: {str(e)}")
            return {}

    def _evaluate_condition(self, device_data: Dict, trigger: Dict) -> bool:
        """
        Evalúa si se cumple la condición de un trigger para un dispositivo específico.
        """
        try:
            device_id = trigger.get("device_id")
            condition = trigger.get("condition")
            field = trigger.get("field")

            # Verificar si el dispositivo coincide con el trigger
            if device_id != "*" and device_id != device_data.get("device_id"):
                return False

            # Obtener el valor del campo
            field_value = device_data.get("data", {}).get(field)
            if field_value is None:
                return False

            # Evaluar la condición
            try:
                # Reemplazar variables en la condición (ej: battery_level < 20)
                local_vars = {"device_id": device_data.get("device_id")}
                for key, value in device_data.get("data", {}).items():
                    local_vars[key] = value

                # Evaluar la condición en un contexto seguro
                return eval(condition, {"__builtins__": None}, local_vars)
            except Exception as e:
                self.logger.error(f"Error al evaluar condición '{condition}': {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"Error al evaluar trigger: {str(e)}")
            return False

    def _execute_action(self, action: Dict, device_data: Dict):
        """Ejecuta una acción específica."""
        try:
            action_type = action.get("type")
            if action_type == "desktop_notification":
                self._send_desktop_notification(action, device_data)
            elif action_type == "stop_high_consumption_workers":
                self._stop_workers(action, device_data)
            elif action_type == "iot_toggle_smart_plug":
                self._iot_toggle_smart_plug(action, device_data)
            elif action_type == "iot_set_ambient_lighting":
                self._iot_set_ambient_lighting(action, device_data)
            elif action_type == "command_voice":
                self._command_voice(action, device_data)
            else:
                self.logger.warning(f"Acción no soportada: {action_type}")
        except Exception as e:
            self.logger.error(f"Error al ejecutar acción: {str(e)}")

    def _send_desktop_notification(self, action: Dict, device_data: Dict):
        """Envía una notificación de escritorio."""
        try:
            title = action.get("title", "AURA Alert")
            message = action.get("message")

            # Reemplazar placeholders con valores reales
            message = message.replace("{{device_id}}", device_data.get("device_id"))
            for key, value in device_data.get("data", {}).items():
                message = message.replace(f"{{{key}}}", str(value))

            # Implementación específica para el sistema operativo
            if platform.system() == "Windows":
                self._send_windows_notification(title, message)
            elif platform.system() == "Darwin":  # macOS
                self._send_mac_notification(title, message)
            elif platform.system() == "Linux":
                self._send_linux_notification(title, message)
            else:
                self.logger.warning(
                    f"Sistema operativo no soportado para notificaciones: {platform.system()}"
                )

        except Exception as e:
            self.logger.error(f"Error al enviar notificación: {str(e)}")

    def _send_windows_notification(self, title: str, message: str):
        """Envía una notificación en Windows usando balloon tips."""
        try:
            import ctypes
            import win32gui
            import win32con

            # Usar el API de Windows para mostrar una notificación
            message_map = {
                win32con.WM_DESTROY: lambda hWnd, wParam, lParam: win32gui.PostQuitMessage(0),
                win32con.WM_COMMAND: lambda hWnd, wParam, lParam: win32gui.PostQuitMessage(0),
            }

            def WindowProc(hWnd, message, wParam, lParam):
                return message_map.get(message)(hWnd, wParam, lParam)

            class MyWindow:
                def __init__(self):
                    self.hwnd = win32gui.CreateWindow(
                        win32con.WS_OVERLAPPEDWINDOW,
                        "Notification",
                        "",
                        win32con.WS_OVERLAPPEDWINDOW,
                        0,
                        0,
                        100,
                        100,
                        None,
                        None,
                        None,
                        None,
                    )
                    win32gui.SetWindowLong(self.hwnd, win32con.GWL_WNDPROC, WindowProc)
                    win32gui.UpdateWindow(self.hwnd)

            # Mostrar notificación usando el API de Shell
            shell32 = ctypes.windll.shell32
            shell32.ShellExecuteW(
                None, "notify", None, f"Title: {title}\nMessage: {message}", None, win32con.SW_SHOW
            )

            # Alternativa usando balloon tip
            # NOTA: El código de balloon tip es complejo y requiere más configuración
            # Para simplificar, usamos ShellExecuteW que muestra una ventana de notificación

        except Exception as e:
            self.logger.error(f"Error al enviar notificación en Windows: {str(e)}")

    def _send_mac_notification(self, title: str, message: str):
        """Envía una notificación en macOS usando terminal-notifier."""
        try:
            command = f'osascript -e \'display notification "{message}" with title "{title}"\''
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al enviar notificación en macOS: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error al enviar notificación en macOS: {str(e)}")

    def _send_linux_notification(self, title: str, message: str):
        """Envía una notificación en Linux usando notify-send."""
        try:
            command = f"notify-send '{title}' '{message}'"
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al enviar notificación en Linux: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error al enviar notificación en Linux: {str(e)}")

    def _stop_workers(self, action: Dict, device_data: Dict):
        """Detiene los workers de alto consumo para un dispositivo específico."""
        try:
            device_id = action.get("device_id", device_data.get("device_id"))
            if not device_id:
                raise ValueError("No se especificó un ID de dispositivo para detener workers.")

            # Reemplazar placeholders
            device_id = device_id.replace("{{device_id}}", device_data.get("device_id"))

            # Aquí iría la lógica para detener los workers en el dispositivo móvil
            # Por ejemplo, enviar un comando SSH al dispositivo para detener procesos
            self.logger.info(f"Deteniendo workers de alto consumo para el dispositivo {device_id}")

            # Ejemplo de comando SSH (simulado)
            # ssh_command = f"ssh user@{device_id} 'pkill -f high_consumption_worker'"
            # subprocess.run(ssh_command, shell=True, check=True)

            # Para este ejemplo, solo registramos la acción
            self.logger.info(f"Acción simulada: Detener workers para {device_id}")

        except Exception as e:
            self.logger.error(f"Error al detener workers: {str(e)}")

    def _iot_toggle_smart_plug(self, action: Dict, device_data: Dict):
        """Enciende/apaga un smart plug conectado al cargador de pared."""
        try:
            device_id = action.get("device_id", device_data.get("device_id", "charger_plug"))
            device_id = str(device_id).replace("{{device_id}}", str(device_data.get("device_id")))
            state = action.get("state", True)
            device_id = device_id.replace("{{device_id}}", str(device_data.get("device_id")))
            res = self.iot.toggle_smart_plug(device_id, state)
            self.logger.info(f"IoT: smart_plug {device_id} -> {'ON' if state else 'OFF'} | {res}")
        except Exception as e:
            self.logger.error(f"Error en acción IoT toggle_smart_plug: {e}")

    def _iot_set_ambient_lighting(self, action: Dict, device_data: Dict):
        """Cambia iluminación ambiental para indicar estado del bot."""
        try:
            room_id = action.get("room_id", "game_room")
            color = action.get("color", "#DC143C")
            res = self.iot.set_ambient_lighting(room_id, color)
            self.logger.info(f"IoT: luz ambiental {room_id} -> {color} | {res}")
        except Exception as e:
            self.logger.error(f"Error en acción IoT set_ambient_lighting: {e}")

    def _command_voice(self, action: Dict, device_data: Dict):
        """Enruta comandos de voz hacia acciones físicas."""
        try:
            text = action.get("text", "")
            if not text:
                return
            lowered = text.lower()
            if "Modo Minería Avanzado" in lowered:
                # Activar bot y luz encuentro activo
                self._iot_set_ambient_lighting(
                    {"room_id": action.get("room_id", "game_room"), "color": "#DC143C"},
                    device_data,
                )
                self.logger.info("Voz -> RollerCoin Bot ACTIVADO")
            elif "Modo Minero" in lowered or "miner" in lowered:
                self._iot_set_ambient_lighting(
                    {"room_id": action.get("room_id", "game_room"), "color": "#DC143C"},
                    device_data,
                )
                self.logger.info("Voz -> RollerCoin Bot ACTIVADO (alias)")
            elif "parar minería" in lowered or "stop miner" in lowered:
                self._iot_set_ambient_lighting(
                    {"room_id": action.get("room_id", "game_room"), "color": "#000000"},
                    device_data,
                )
                self.logger.info("Voz -> RollerCoin Bot APAGADO")
        except Exception as e:
            self.logger.error(f"Error en acción command_voice: {e}")

    def _update_canvas(self):
        """Actualiza el canvas del HUD vectorial (desducción de frecuencia)."""
        try:
            now = time.time()
            interval = 10  # segundos
            if hasattr(self, "_last_canvas_update") and now - self._last_canvas_update < interval:
                return
            self._last_canvas_update = now
            from AURA_Core.hud.canvas_generator import run_canvas_update

            run_canvas_update()
        except Exception as e:
            self.logger.error(f"Error actualizando canvas HUD: {e}")

    def _start_voice_stream(self):
        """Inicia el stream de audio bidireccional con VAD local y eventos al HUD."""
        if self._voice_active:
            return
        try:
            from AURA_Core.voice.audio_streamer import AudioStreamer
            from AURA_Core.voice.transcriber import Transcriber

            streamer = AudioStreamer(
                on_speech_detected=self._on_speech_segment,
                sample_rate=16000,
                frame_duration_ms=30,
                vad_aggressiveness=2,
            )
            self._voice_stream = streamer
            self._transcriber = Transcriber()
            self._voice_active = True
            streamer.start()
            self._broadcast_ws("voice_stream_start", {"status": "active"})
            self.logger.info("Canal de voz iniciado (stream + VAD).")
        except Exception as e:
            self.logger.error(f"Error iniciando voice stream: {e}")

    def _stop_voice_stream(self):
        if not self._voice_active:
            return
        try:
            if self._voice_stream:
                self._voice_stream.stop()
            self._voice_active = False
            self._broadcast_ws("voice_stream_end", {"status": "inactive"})
            self.logger.info("Canal de voz detenido.")
        except Exception as e:
            self.logger.error(f"Error deteniendo voice stream: {e}")

    def _on_speech_segment(self, audio_bytes: bytes):
        try:
            if not self._voice_active:
                return
            self._broadcast_ws("voice_stream_start", {"status": "speech_detected"})
            text = self._transcriber.transcribe(audio_bytes)
            if text:
                self._handle_voice_command(text)
            self._broadcast_ws("voice_stream_end", {"status": "speech_processed"})
        except Exception as e:
            self.logger.error(f"Error procesando segmento de voz: {e}")

    def _handle_voice_command(self, text: str):
        self.logger.info("Comando de voz recibido: %s", text)
        self.emote.set_state(AvatarState.SPEAKING)
        payload = {"text": text, "source": "voice"}
        self._broadcast_ws("voice_command", payload)
        self.emote.set_state(AvatarState.IDLE)

    def _check_rules(self):
        """Revisa todas las reglas contra los datos de telemetría disponibles."""
        try:
            telemetry_data = self._load_telemetry_data()
            current_time = time.time()

            if current_time - self.last_checked < self.check_interval:
                return

            if not self._voice_active:
                self._start_voice_stream()

            self.last_checked = current_time
            self.logger.info("Revisando reglas contra datos de telemetría...")
            self._update_canvas()
            self.emote.set_state(AvatarState.THINKING)
            for device_id, entries in telemetry_data.items():
                if not entries:
                    continue
                latest_entry = entries[-1]
                device_data = latest_entry
                for rule in self.rules:
                    trigger = rule.get("trigger")
                    if not trigger:
                        continue
                    if self._evaluate_condition(device_data, trigger):
                        self.logger.info(
                            f"Trigger activado para dispositivo {device_id}: {rule.get('description')}"
                        )
                        for action in rule.get("actions", []):
                            self._execute_action(action, device_data)
            self.emote.set_state(AvatarState.IDLE)
        except Exception as e:
            self.logger.error(f"Error al revisar reglas: {str(e)}")

    def _broadcast_ws(self, event: str, payload: Any) -> None:
        """Reenvía eventos por WebSocket a clientes registrados con validación de seguridad."""
        try:
            # Fase 29: Validación estricta anti-confusión de tipos
            if isinstance(payload, (dict, list)):
                InputValidator.prevent_prototype_pollution(payload)

            message = json.dumps({"event": event, "payload": payload})
            if hasattr(self, "send"):
                self.send(message)
        except SecurityValidationError as e:
            self.logger.error(f"Security Block: {e}")
            # Alerta de seguridad auto-generada
            security_payload = {
                "level": "CRITICAL",
                "message": str(e),
                "type": "type_confusion_attempt",
            }
            # Evitamos bucle infinito si la alerta misma falla (aunque es un dict controlado)
            try:
                msg = json.dumps({"event": "security_alert", "payload": security_payload})
                if hasattr(self, "send"):
                    self.send(msg)
            except:
                pass
        except Exception as e:
            self.logger.error(f"Error enviando WebSocket: {e}")

    def send(self, message: str) -> None:
        try:
            # Fase 29: Validación de entrada (Type Enforcement)
            InputValidator.enforce_type(message, str, "websocket_incoming_message")

            data = json.loads(message)
            # Validar estructura básica
            InputValidator.validate_payload(data, {"event": str, "payload": object})

            event = data.get("event")
            payload = data.get("payload")

            if event == "morning_briefing":
                self.logger.info("Recibido briefing matutino por WS")
        except SecurityValidationError as e:
            self.logger.warning(f"Rejected malicious/malformed WS message: {e}")
        except Exception as e:
            self.logger.error(f"WS message error: {e}")

    def _ws_receive_telemetry(self, telemetry_packet: dict):
        """Recibe telemetría desde WS (app Android) y la inyecta en rules.json."""
        device_id = telemetry_packet.get("device_id", "unknown")
        battery = telemetry_packet.get("battery_level", 100)
        cpu = telemetry_packet.get("cpu_usage", 0)
        temp = telemetry_packet.get("temperature", 30)
        connection = telemetry_packet.get("connection_status", "active")
        self.emote.set_state(AvatarState.READING)
        self._inject_telemetry(device_id, battery, cpu, temp, connection)

        # ── Replicar eventos críticos a N8N (asíncrono, no bloqueante) ──
        if battery < 20:
            self.logger.info(
                f"[IoT REAL] Batería baja en {device_id}: {battery}% → apagando smart plug"
            )
            self.iot.toggle_smart_plug(f"charger_{device_id}", True)
            n8n_bridge.trigger_event_replication(
                "low_battery",
                {
                    "device_id": device_id,
                    "battery_level": battery,
                    "cpu_usage": cpu,
                    "temperature": temp,
                },
            )
        if cpu > 90:
            self.logger.info(f"[IoT REAL] CPU alta en {device_id}: {cpu}% → luz roja")
            self.iot.set_ambient_lighting("game_room", "#FF0000")
            n8n_bridge.trigger_event_replication(
                "high_cpu",
                {
                    "device_id": device_id,
                    "battery_level": battery,
                    "cpu_usage": cpu,
                    "temperature": temp,
                },
            )
        if connection == "inactive" or connection == "disconnected":
            n8n_bridge.trigger_event_replication(
                "connection_lost",
                {"device_id": device_id, "battery_level": battery, "connection_status": connection},
            )
        self.emote.set_state(AvatarState.IDLE)

    def _inject_telemetry(
        self, device_id: str, battery: int, cpu: int, temp: float, connection: str
    ):
        import os, json, time

        now = time.time()
        entry = {
            "device_id": device_id,
            "data": {
                "battery_level": battery,
                "cpu_usage": cpu,
                "temperature": temp,
                "connection_status": connection,
            },
        }
        path = self.telemetry_file
        existing = {}
        if os.path.exists(path):
            try:
                with open(path) as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        existing.setdefault(device_id, []).append(entry)
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)

    def run(self):
        """Ejecuta el bucle principal del EventManager."""
        self.logger.info("Iniciando EventManager...")
        self.logger.info(f"Revisión de reglas cada {self.check_interval} segundos.")

        try:
            while True:
                self._check_rules()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self._stop_voice_stream()
            self.logger.info("Deteniendo EventManager...")
        except Exception as e:
            self._stop_voice_stream()
            self.logger.error(f"Error en el bucle principal: {str(e)}")
            sys.exit(1)


def main():
    """Punto de entrada principal del EventManager."""
    config = {
        "rules_file": "rules.json",
        "check_interval": 30,
        "telemetry_file": "telemetry_history.json",
    }

    event_manager = EventManager(config)

    try:
        event_manager.run()
    except Exception as e:
        event_manager.logger.error(f"Error en el EventManager: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
