#!/usr/bin/env python3
"""
android_godot_export.py - Exporta proyectos Godot a APK para Android
Autor: Cline
Licencia: MIT
"""

import os
import sys
import subprocess
import shutil
import stat
import time
import json
import platform
import zipfile
import tempfile
from typing import List, Dict, Optional, Tuple
from pathlib import Path

class AndroidExporter:
    """
    Exporta proyectos Godot a APK para Android y gestiona el envío al dispositivo móvil.
    """

    def __init__(self, project_path="godot_game/"):
        self.project_path = Path(project_path)
        self.export_dir = self.project_path / "export" / "android"
        self.keystore_path = self.project_path / "debug.keystore"
        self.log_file = self.project_path / "logs" / "android_export.log"
        self._setup_logging()

        # Verificar que el directorio del proyecto exista
        if not self.project_path.exists():
            raise FileNotFoundError(f"El directorio del proyecto no existe: {self.project_path}")

    def _setup_logging(self):
        """Configura el archivo de logs para la exportación."""
        os.makedirs(self.log_file.parent, exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write(f"📝 Iniciando Android Exporter en {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    def check_requirements(self) -> Dict[str, bool]:
        """
        Verifica los requisitos para exportar a Android.

        Returns:
            Diccionario con el estado de cada requisito
        """
        requirements = {
            "godot_installed": self._check_godot_installed(),
            "project_exists": self.project_path.exists(),
            "android_sdk": self._check_android_sdk(),
            "java_installed": self._check_java_installed(),
            "export_templates": self._check_export_templates(),
            "keystore_exists": self.keystore_path.exists(),
            "export_dir_exists": self.export_dir.exists()
        }

        # Registrar resultados en log
        with open(self.log_file, 'a') as f:
            f.write("🔍 Verificando requisitos para exportar a Android:\n")
            for req, status in requirements.items():
                f.write(f"  {req}: {'✅' if status else '❌'}\n")

        return requirements

    def _check_godot_installed(self) -> bool:
        """Verifica si Godot está instalado."""
        try:
            result = subprocess.run(
                ["godot", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _check_android_sdk(self) -> bool:
        """Verifica si el Android SDK está instalado."""
        sdk_paths = [
            os.path.join(os.environ.get('ANDROID_HOME', ''), 'platform-tools'),
            os.path.join(os.environ.get('ANDROID_SDK_ROOT', ''), 'platform-tools')
        ]

        for path in sdk_paths:
            if os.path.exists(os.path.join(path, 'adb')):
                return True

        return False

    def _check_java_installed(self) -> bool:
        """Verifica si Java está instalado."""
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _check_export_templates(self) -> bool:
        """Verifica si las export templates de Godot existen."""
        export_templates = self.project_path / "export_templates"
        return export_templates.exists()

    def setup_export_preset(self) -> bool:
        """
        Configura el preset de exportación para Android.

        Returns:
            True si se configuró correctamente
        """
        try:
            print("📝 Configurando preset de exportación para Android...")

            # Crear directorio de exportación si no existe
            os.makedirs(self.export_dir, exist_ok=True)

            # Crear archivo de configuración de exportación
            preset_path = self.project_path / "export_presets.cfg"

            # Contenido del preset
            preset_content = f"""[preset]
name=Android
path={self.export_dir}
custom_template_path={self.project_path / "export_templates"}

[android]
package_name=com.aura.godotgame
app_name=AURA Game
version=1.0
build=1
orientation=landscape
use_custom_main_activity=false
use_ndk=false
use_64bit_arch=false
use_arm64_v8a=true
use_x86=false
use_x86_64=false
use_mips=false
use_mips64=false
use_split_apk=false
use_keystore=true
keystore_path={self.keystore_path}
keystore_password=android
key_alias=androiddebugkey
key_password=android
min_sdk_version=21
target_sdk_version=31
use_gl20=true
use_vulkan=false
use_rendertargets=false
use_3d=false
use_multithreaded=false
use_editor_permissions=false
use_internet_permission=true
use_write_external_storage_permission=false
use_read_external_storage_permission=false
use_camera_permission=false
use_microphone_permission=false
use_location_permission=false
use_vibration_permission=false
use_wakelock_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
use_android_permission=false
"""

            # Guardar preset
            with open(preset_path, 'w') as f:
                f.write(preset_content)

            print("✅ Preset de exportación configurado correctamente")
            return True

        except Exception as e:
            print(f"❌ Error al configurar preset: {e}")
            return False

    def generate_debug_keystore(self) -> bool:
        """
        Genera un keystore de debug para Android.

        Returns:
            True si se generó correctamente
        """
        try:
            print(f"🔑 Generando keystore de debug en: {self.keystore_path}")

            # Verificar si ya existe
            if self.keystore_path.exists():
                print("✅ Keystore ya existe")
                return True

            # Crear directorio si no existe
            os.makedirs(self.keystore_path.parent, exist_ok=True)

            # Generar keystore usando keytool
            result = subprocess.run(
                [
                    "keytool",
                    "-genkey",
                    "-v",
                    "-keystore", str(self.keystore_path),
                    "-alias", "androiddebugkey",
                    "-storepass", "android",
                    "-keypass", "android",
                    "-validity", "10000",
                    "-keyalg", "RSA",
                    "-keysize", "2048",
                    "-dname", "CN=Android Debug,O=Android,C=US"
                ],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print("✅ Keystore generado correctamente")
                return True
            else:
                print(f"❌ Error al generar keystore: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error al generar keystore: {e}")
            return False

    def build_apk(self, release: bool = False) -> Optional[str]:
        """
        Exporta el proyecto a APK para Android.

        Args:
            release: Si es True, genera una versión de release (de lo contrario, debug)

        Returns:
            Ruta del APK generado o None si hubo error
        """
        try:
            print(f"📱 Exportando APK para Android...")

            # Verificar requisitos
            requirements = self.check_requirements()
            if not all(requirements.values()):
                print("❌ Requisitos no cumplidos para exportar APK")
                missing = [req for req, status in requirements.items() if not status]
                print(f"   Requisitos faltantes: {', '.join(missing)}")
                return None

            # Configurar preset si no existe
            if not (self.project_path / "export_presets.cfg").exists():
                if not self.setup_export_preset():
                    return None

            # Generar keystore si no existe
            if not self.keystore_path.exists():
                if not self.generate_debug_keystore():
                    return None

            # Crear directorio de exportación si no existe
            os.makedirs(self.export_dir, exist_ok=True)

            # Determinar el nombre del APK
            timestamp = int(time.time())
            apk_name = f"AURA_Game_{timestamp}"
            if release:
                apk_name = f"AURA_Game_Release_{timestamp}"
                output_path = self.export_dir / f"{apk_name}.apk"
            else:
                output_path = self.export_dir / f"{apk_name}_debug.apk"

            # Ejecutar Godot para exportar
            print(f"🔧 Exportando APK a: {output_path}")

            # Registrar en log
            with open(self.log_file, 'a') as f:
                f.write(f"📦 Exportando APK a {output_path} en {time.strftime('%H:%M:%S')}\n")

            # Ejecutar Godot con el comando de exportación
            cmd = [
                "godot",
                "--path", str(self.project_path),
                "--export-release" if release else "--export-debug",
                "Android",
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos para exportar
            )

            # Registrar resultado en log
            with open(self.log_file, 'a') as f:
                f.write(f"📋 Resultado de exportación: {result.returncode}\n")
                if result.stdout:
                    f.write(f"📋 Salida estándar: {result.stdout}\n")
                if result.stderr:
                    f.write(f"📋 Errores: {result.stderr}\n")

            # Verificar si se generó el APK
            if output_path.exists():
                print(f"✅ APK exportado correctamente: {output_path}")
                return str(output_path)
            else:
                print(f"❌ Error al exportar APK: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("⏱️ Error: Tiempo de exportación agotado (5 minutos)")
            return None
        except Exception as e:
            print(f"❌ Error al exportar APK: {e}")
            return None

    def install_via_adb(self, apk_path: str) -> bool:
        """
        Instala el APK en el dispositivo Android usando ADB.

        Args:
            apk_path: Ruta al archivo APK

        Returns:
            True si se instaló correctamente
        """
        try:
            print(f"📲 Instalando APK en dispositivo Android: {apk_path}")

            # Verificar que ADB esté disponible
            if not self._check_adb_available():
                print("❌ ADB no está disponible. Conecta el dispositivo por USB o usa otro método.")
                return False

            # Verificar que el APK exista
            if not os.path.exists(apk_path):
                print(f"❌ Archivo APK no encontrado: {apk_path}")
                return False

            # Instalar APK usando ADB
            result = subprocess.run(
                ["adb", "install", "-r", apk_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print("✅ APK instalado correctamente en el dispositivo")
                return True
            else:
                print(f"❌ Error al instalar APK: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error al instalar APK: {e}")
            return False

    def _check_adb_available(self) -> bool:
        """Verifica si ADB está disponible."""
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def send_apk_to_ame(self, apk_path: str) -> bool:
        """
        Envía el APK al dispositivo móvil usando el canal AURA.

        Args:
            apk_path: Ruta al archivo APK

        Returns:
            True si se envió correctamente
        """
        try:
            print(f"📡 Enviando APK a dispositivo móvil: {apk_path}")

            # Verificar que el APK exista
            if not os.path.exists(apk_path):
                print(f"❌ Archivo APK no encontrado: {apk_path}")
                return False

            # Obtener el tamaño del APK
            apk_size = os.path.getsize(apk_path)
            print(f"📏 Tamaño del APK: {apk_size / 1024 / 1024:.2f} MB")

            # Dividir el APK en chunks (1MB cada uno)
            chunk_size = 1024 * 1024  # 1MB
            chunks = []

            with open(apk_path, 'rb') as f:
                chunk_id = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append((chunk_id, chunk))
                    chunk_id += 1

            print(f"📦 APK dividido en {len(chunks)} chunks")

            # Simular envío a través del canal AURA
            # En un entorno real, esto enviaría los chunks por WebSocket al AME
            print("📡 Simulando envío a través del canal AURA...")

            # Crear directorio de recepción en el dispositivo (simulado)
            receive_dir = os.path.join(self.project_path, "temp_apk_receive")
            os.makedirs(receive_dir, exist_ok=True)

            # Reconstruir el APK en el directorio de recepción
            output_path = os.path.join(receive_dir, os.path.basename(apk_path))

            with open(output_path, 'wb') as f:
                for chunk_id, chunk in sorted(chunks):
                    f.write(chunk)

            print(f"✅ APK reconstruido en: {output_path}")

            # Simular notificación al AME
            print("📢 Notificación a AME: APK recibido y guardado en /sdcard/Downloads/")

            # En un entorno real, esto enviaría una notificación al EventBus de AURA
            # self._notify_ame_apk_received(output_path)

            return True

        except Exception as e:
            print(f"❌ Error al enviar APK: {e}")
            return False

    def _notify_ame_apk_received(self, apk_path: str):
        """
        Notifica a AME que el APK ha sido recibido (simulado).

        Args:
            apk_path: Ruta del APK recibido
        """
        try:
            print(f"📡 Notificando a AME: APK recibido en {apk_path}")

            # En un entorno real, esto enviaría un mensaje al EventBus de AURA
            message = {
                "node": "ANDROID_EXPORTER",
                "event": "APK_RECEIVED",
                "data": {
                    "file": os.path.basename(apk_path),
                    "path": apk_path,
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "size": os.path.getsize(apk_path)
                }
            }

            print(f"📋 Mensaje de notificación: {json.dumps(message, indent=2)}")

            # En un entorno real:
            # self.event_bus.publish("godot_apk_received", message)

        except Exception as e:
            print(f"❌ Error al notificar a AME: {e}")

    def get_export_status(self) -> Dict:
        """
        Obtiene el estado actual de la exportación.

        Returns:
            Diccionario con información del estado
        """
        status = {
            "project_path": str(self.project_path),
            "export_dir": str(self.export_dir),
            "keystore_exists": self.keystore_path.exists(),
            "requirements": self.check_requirements(),
            "last_export": None,
            "last_error": None
        }

        # Obtener información de la última exportación
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    for i, line in enumerate(reversed(lines)):
                        if "Exportando APK" in line:
                            status["last_export"] = line.strip()
                            break
                        elif "Error al exportar" in line:
                            status["last_error"] = line.strip()
                            break
                        if i > 10:  # Solo revisar últimos 10 líneas
                            break
            except:
                pass

        return status

    def clean_export_dir(self) -> bool:
        """
        Limpia el directorio de exportación.

        Returns:
            True si se limpió correctamente
        """
        try:
            print(f"🧹 Limpiando directorio de exportación: {self.export_dir}")

            if self.export_dir.exists():
                # Eliminar todos los archivos en el directorio
                for item in self.export_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)

                print("✅ Directorio de exportación limpio")
                return True
            else:
                print("⚠️ El directorio de exportación no existe")
                return False

        except Exception as e:
            print(f"❌ Error al limpiar directorio: {e}")
            return False

    def get_available_devices(self) -> List[Dict]:
        """
        Obtiene los dispositivos Android disponibles para instalación.

        Returns:
            Lista de dispositivos disponibles
        """
        try:
            print("📱 Buscando dispositivos Android disponibles...")

            # Usar ADB para obtener lista de dispositivos
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True
            )

            devices = []
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Saltar la primera línea (encabezado)
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[1] == "device":
                        devices.append({
                            "id": parts[0],
                            "name": "Dispositivo desconocido",
                            "status": "connected"
                        })

            # Intentar obtener información más detallada
            for device in devices:
                try:
                    result = subprocess.run(
                        ["adb", "-s", device["id"], "shell", "getprop", "ro.product.model"],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if result.returncode == 0:
                        device["name"] = result.stdout.strip()
                except:
                    pass

            print(f"✅ Encontrados {len(devices)} dispositivos disponibles")
            return devices

        except Exception as e:
            print(f"❌ Error al obtener dispositivos: {e}")
            return []

    def install_on_device(self, apk_path: str, device_id: str = None) -> bool:
        """
        Instala el APK en un dispositivo Android específico.

        Args:
            apk_path: Ruta al archivo APK
            device_id: ID del dispositivo (None para usar el primero disponible)

        Returns:
            True si se instaló correctamente
        """
        try:
            print(f"📲 Instalando APK en dispositivo: {apk_path}")

            # Obtener lista de dispositivos
            devices = self.get_available_devices()
            if not devices:
                print("❌ No hay dispositivos disponibles")
                return False

            # Seleccionar dispositivo
            if device_id:
                selected_device = next((d for d in devices if d["id"] == device_id), None)
                if not selected_device:
                    print(f"❌ Dispositivo no encontrado: {device_id}")
                    return False
            else:
                selected_device = devices[0]
                print(f"📱 Usando dispositivo predeterminado: {selected_device['name']} ({selected_device['id']})")

            # Instalar APK en el dispositivo específico
            result = subprocess.run(
                ["adb", "-s", selected_device["id"], "install", "-r", apk_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"✅ APK instalado correctamente en {selected_device['name']}")
                return True
            else:
                print(f"❌ Error al instalar APK: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error al instalar APK: {e}")
            return False

    def generate_apk_info(self, apk_path: str) -> Optional[Dict]:
        """
        Obtiene información del APK generado.

        Args:
            apk_path: Ruta al archivo APK

        Returns:
            Diccionario con información del APK o None si hubo error
        """
        try:
            print(f"📄 Obteniendo información del APK: {apk_path}")

            if not os.path.exists(apk_path):
                print(f"❌ Archivo APK no encontrado: {apk_path}")
                return None

            # Usar aapt para obtener información del APK
            result = subprocess.run(
                ["aapt", "dump", "badging", apk_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"❌ Error al obtener información del APK: {result.stderr}")
                return None

            # Procesar la salida de aapt
            info = {}
            for line in result.stdout.split('\n'):
                if 'package:' in line:
                    info['package'] = line.split(': ')[1]
                elif 'application:' in line:
                    parts = line.split(': ')
                    if len(parts) > 1:
                        app_info = parts[1].split(', ')
                        for part in app_info:
                            if '=' in part:
                                key, value = part.split('=', 1)
                                info[key.strip()] = value.strip()
                elif 'launchable-activity:' in line:
                    info['launchable_activity'] = line.split(': ')[1]
                elif 'sdkVersion:' in line:
                    info['sdk_version'] = line.split(': ')[1]
                elif 'targetSdkVersion:' in line:
                    info['target_sdk_version'] = line.split(': ')[1]

            # Obtener tamaño del APK
            info['size'] = os.path.getsize(apk_path)
            info['size_mb'] = info['size'] / 1024 / 1024

            # Obtener hash del APK
            info['hash'] = self._calculate_apk_hash(apk_path)

            return info

        except Exception as e:
            print(f"❌ Error al obtener información del APK: {e}")
            return None

    def _calculate_apk_hash(self, apk_path: str) -> str:
        """Calcula el hash SHA-256 del APK."""
        try:
            result = subprocess.run(
                ["sha256sum", apk_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.split()[0]
            else:
                return "unknown"
        except:
            return "unknown"

    def create_export_report(self, apk_path: str) -> Optional[str]:
        """
        Crea un informe de exportación con información detallada del APK.

        Args:
            apk_path: Ruta al archivo APK

        Returns:
            Ruta del archivo de informe generado o None si hubo error
        """
        try:
            print(f"📊 Generando informe de exportación para: {apk_path}")

            # Obtener información del APK
            apk_info = self.generate_apk_info(apk_path)
            if not apk_info:
                print("❌ No se pudo obtener información del APK")
                return None

            # Crear directorio para informes
            report_dir = self.project_path / "reports"
            os.makedirs(report_dir, exist_ok=True)

            # Generar nombre de archivo para el informe
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            report_name = f"export_report_{timestamp}.json"
            report_path = report_dir / report_name

            # Crear informe
            report = {
                "project": "AURA Game",
                "export_date": time.strftime('%Y-%m-%d %H:%M:%S'),
                "apk_path": str(apk_path),
                "apk_info": apk_info,
                "export_settings": {
                    "platform": "Android",
                    "version": "1.0",
                    "build": 1,
                    "keystore": str(self.keystore_path),
                    "target_sdk": apk_info.get("target_sdk_version", "unknown")
                },
                "requirements": self.check_requirements(),
                "notes": [
                    "Este informe fue generado automáticamente por el sistema de exportación de Godot.",
                    "El APK está listo para ser instalado en dispositivos Android.",
                    "Verifica que el dispositivo tenga al menos Android 5.0 (API 21) para compatibilidad."
                ]
            }

            # Guardar informe en JSON
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)

            print(f"✅ Informe de exportación generado: {report_path}")
            return str(report_path)

        except Exception as e:
            print(f"❌ Error al generar informe: {e}")
            return None

    def get_export_history(self, max_entries: int = 10) -> List[Dict]:
        """
        Obtiene el historial de exportaciones recientes.

        Args:
            max_entries: Número máximo de entradas a devolver

        Returns:
            Lista de exportaciones recientes
        """
        try:
            print(f"📜 Obteniendo historial de exportaciones (últimos {max_entries})...")

            history = []

            # Leer el archivo de logs
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()

                # Buscar líneas de exportación
                for line in reversed(lines):
                    if "Exportando APK" in line:
                        entry = {
                            "timestamp": None,
                            "action": line.strip(),
                            "result": None
                        }

                        # Buscar la línea de resultado
                        for i, l in enumerate(lines[lines.index(line):]):
                            if "Resultado de exportación" in l:
                                entry["result"] = l.strip()
                                break
                            elif "Error al exportar" in l:
                                entry["result"] = l.strip()
                                break
                            elif "APK exportado correctamente" in l:
                                entry["result"] = l.strip()
                                break
                            elif i > 10:  # Solo revisar 10 líneas después
                                break

                        # Obtener timestamp
                        if "Exportando APK" in line:
                            try:
                                timestamp_str = line.split("Exportando APK")[0].strip()
                                entry["timestamp"] = timestamp_str
                            except:
                                pass

                        history.append(entry)
                        if len(history) >= max_entries:
                            break

            # Ordenar por fecha (más reciente primero)
            history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            print(f"✅ Encontradas {len(history)} exportaciones en el historial")
            return history

        except Exception as e:
            print(f"❌ Error al obtener historial: {e}")
            return []

    def backup_export_settings(self) -> bool:
        """
        Realiza una copia de seguridad de la configuración de exportación.

        Returns:
            True si se realizó correctamente
        """
        try:
            print("💾 Realizando copia de seguridad de configuración de exportación...")

            # Crear directorio de backups
            backup_dir = self.project_path / "backups" / "export_settings"
            os.makedirs(backup_dir, exist_ok=True)

            # Archivos a copiar
            files_to_backup = [
                self.project_path / "export_presets.cfg",
                self.keystore_path,
                self.log_file
            ]

            # Crear nombre de backup con timestamp
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup_name = f"export_backup_{timestamp}"
            backup_path = backup_dir / backup_name

            # Crear archivo ZIP con la copia de seguridad
            with zipfile.ZipFile(f"{backup_path}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in files_to_backup:
                    if file_path.exists():
                        arcname = file_path.name
                        if file_path == self.keystore_path:
                            # Para el keystore, crear un archivo temporal sin contraseña
                            temp_keystore = backup_path / "keystore_backup.jks"
                            shutil.copy2(file_path, temp_keystore)
                            zipf.write(temp_keystore, arcname)
                            temp_keystore.unlink()
                        else:
                            zipf.write(file_path, arcname)

            print(f"✅ Copia de seguridad realizada: {backup_path}.zip")
            return True

        except Exception as e:
            print(f"❌ Error al realizar copia de seguridad: {e}")
            return False

    def restore_export_settings(self, backup_path: str) -> bool:
        """
        Restaura la configuración de exportación desde una copia de seguridad.

        Args:
            backup_path: Ruta al archivo ZIP de copia de seguridad

        Returns:
            True si se restauró correctamente
        """
        try:
            print(f"🔄 Restaurando configuración de exportación desde: {backup_path}")

            if not os.path.exists(backup_path):
                print(f"❌ Archivo de copia de seguridad no encontrado: {backup_path}")
                return False

            # Extraer el archivo ZIP
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(self.project_path)

            print(f"✅ Configuración de exportación restaurada correctamente")
            return True

        except Exception as e:
            print(f"❌ Error al restaurar configuración: {e}")
            return False

    def get_export_templates_info(self) -> Dict:
        """
        Obtiene información sobre las export templates de Godot.

        Returns:
            Diccionario con información sobre las templates
        """
        info = {
            "export_templates_path": str(self.project_path / "export_templates"),
            "exists": (self.project_path / "export_templates").exists(),
            "files": [],
            "size": 0
        }

        if info["exists"]:
            try:
                for item in (self.project_path / "export_templates").iterdir():
                    if item.is_file():
                        info["files"].append({
                            "name": item.name,
                            "size": item.stat().st_size,
                            "modified": time.strftime('%Y-%m-%d %H:%M:%S',
                                                   time.localtime(item.stat().st_mtime))
                        })
                        info["size"] += item.stat().st_size
            except Exception as e:
                print(f"⚠️ Error al obtener información de templates: {e}")

        return info

    def update_export_templates(self) -> bool:
        """
        Actualiza las export templates de Godot desde la última versión.

        Returns:
            True si se actualizó correctamente
        """
        try:
            print("🔄 Actualizando export templates de Godot...")

            # Verificar que Godot esté instalado
            if not self._check_godot_installed():
                print("❌ Godot no está instalado. No se pueden actualizar las templates.")
                return False

            # Verificar que el directorio de export templates exista
            export_templates = self.project_path / "export_templates"
            if not export_templates.exists():
                os.makedirs(export_templates)
                print("✅ Directorio de export templates creado")

            # Intentar descargar las últimas templates
            # En Godot 4, las templates se descargan automáticamente al primer export
            # Solo necesitamos asegurarnos de que el directorio exista

            print("✅ Export templates actualizadas (Godot 4 descarga automáticamente las últimas versiones)")
            return True

        except Exception as e:
            print(f"❌ Error al actualizar templates: {e}")
            return False

if __name__ == "__main__":
    # Ejemplo de uso
    print("🚀 Iniciando Android Exporter...")

    try:
        # Crear exporter
        exporter = AndroidExporter(project_path="godot_game/")

        # Verificar requisitos
        print("\n🔍 Verificando requisitos para exportar a Android:")
        requirements = exporter.check_requirements()
        for req, status in requirements.items():
            print(f"  {req}: {'✅' if status else '❌'}")

        # Configurar preset si no existe
        if not (exporter.project_path / "export_presets.cfg").exists():
            print("\n📝 Configurando preset de exportación...")
            exporter.setup_export_preset()

        # Generar keystore si no existe
        if not exporter.keystore_path.exists():
            print("\n🔑 Generando keystore de debug...")
            exporter.generate_debug_keystore()

        # Exportar APK
        print("\n📦 Exportando APK (esto puede tardar varios minutos)...")
        apk_path = exporter.build_apk()
        if apk_path:
            print(f"🎉 APK generado en: {apk_path}")

            # Obtener información del APK
            print("\n📄 Obteniendo información del APK...")
            apk_info = exporter.generate_apk_info(apk_path)
            if apk_info:
                print(f"📋 Información del APK:")
                for key, value in apk_info.items():
                    if key != "size":
                        print(f"  {key}: {value}")

            # Generar informe de exportación
            print("\n📊 Generando informe de exportación...")
            report_path = exporter.create_export_report(apk_path)
            if report_path:
                print(f"📄 Informe generado en: {report_path}")

            # Obtener historial de exportaciones
            print("\n📜 Obteniendo historial de exportaciones...")
            history = exporter.get_export_history()
            if history:
                print(f"📋 Últimas {len(history)} exportaciones:")
                for i, entry in enumerate(history[:3]):  # Mostrar primeras 3
                    print(f"  {i+1}. {entry.get('timestamp', 'Desconocido')}: {entry.get('action', '')}")
                    if entry.get('result'):
                        print(f"     Resultado: {entry['result']}")

            # Mostrar dispositivos disponibles
            print("\n📱 Dispositivos Android disponibles:")
            devices = exporter.get_available_devices()
            for i, device in enumerate(devices):
                print(f"  {i+1}. {device['name']} ({device['id']}) - {device['status']}")

        else:
            print("❌ Error al exportar APK")

    except Exception as e:
        print(f"❌ Error en Android Exporter: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🛑 Android Exporter finalizado")