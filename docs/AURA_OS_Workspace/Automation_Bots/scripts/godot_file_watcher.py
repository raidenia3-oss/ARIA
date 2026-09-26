#!/usr/bin/env python3
"""
godot_file_watcher.py - Vigila cambios en archivos GDScript y escenas .tscn
para hacer hot-reload automático en Godot 4.x

Autor: Cline
Licencia: MIT
"""

import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from scripts.godot_controller import GodotController
import json
import threading

class GodotFileWatcher:
    """
    Vigila cambios en archivos GDScript y escenas .tscn para hacer hot-reload
    automático en Godot 4.x.
    """

    def __init__(self, project_path="godot_game/", controller=None):
        self.project_path = project_path
        self.controller = controller or GodotController()
        self.observer = None
        self.running = False
        self.event_bus = None  # Para notificar a AURA EventBus

        # Crear directorio de logs si no existe
        os.makedirs("logs/", exist_ok=True)

    def start(self):
        """Inicia el observador de archivos."""
        if self.running:
            print("⚠️ El watcher ya está corriendo")
            return

        print(f"👁️ Vigilando cambios en: {self.project_path}")

        # Crear directorio de logs para el watcher
        log_file = os.path.join("logs", "godot_watcher.log")
        with open(log_file, 'w') as f:
            f.write(f"📝 Iniciando Godot File Watcher en {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Iniciar observador
        event_handler = GodotEventHandler(self.controller, self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.project_path, recursive=True)
        self.observer.start()

        self.running = True
        print("✅ Godot File Watcher activo")

    def stop(self):
        """Detiene el observador de archivos."""
        if not self.running:
            print("⚠️ El watcher ya está detenido")
            return

        print("🛑 Deteniendo Godot File Watcher...")
        self.observer.stop()
        self.observer.join()
        self.running = False
        print("✅ Godot File Watcher detenido")

    def notify_event_bus(self, event_type, file_path, data=None):
        """Notifica a AURA EventBus sobre cambios."""
        if not self.event_bus:
            print("⚠️ No hay conexión a AURA EventBus")
            return

        try:
            message = {
                "node": "GODOT_WATCHER",
                "event": event_type,
                "data": {
                    "file": file_path,
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "data": data
                }
            }

            # Simular notificación a EventBus
            print(f"📡 Notificación a EventBus: {event_type} en {file_path}")
            print(f"📥 Datos: {json.dumps(message, indent=2)}")

            # En un entorno real, esto enviaría a AURA EventBus
            # self.event_bus.publish("godot_event", message)

        except Exception as e:
            print(f"❌ Error al notificar EventBus: {e}")

class GodotEventHandler(FileSystemEventHandler):
    """Maneja eventos del sistema de archivos para Godot."""

    def __init__(self, controller, watcher):
        self.controller = controller
        self.watcher = watcher
        self.last_modified = {}  # Para evitar notificar cambios múltiples

    def on_modified(self, event):
        """Evento cuando un archivo es modificado."""
        if not event.is_directory:
            self._handle_file_change(event)

    def on_created(self, event):
        """Evento cuando un archivo es creado."""
        if not event.is_directory:
            self._handle_file_change(event)

    def _handle_file_change(self, event):
        """Maneja cambios en archivos GDScript o escenas .tscn."""
        file_path = event.src_path
        relative_path = os.path.relpath(file_path, self.watcher.project_path)

        # Evitar notificar cambios múltiples en el mismo archivo
        if relative_path in self.last_modified:
            if time.time() - self.last_modified[relative_path] < 1.0:  # 1 segundo
                return
            else:
                self.last_modified[relative_path] = time.time()

        # Registrar el cambio
        self.last_modified[relative_path] = time.time()

        # Registrar en log
        log_message = f"📝 {time.strftime('%H:%M:%S')} - {relative_path} modificado"
        with open("logs/godot_watcher.log", 'a') as f:
            f.write(log_message + "\n")

        print(log_message)

        # Procesar según el tipo de archivo
        if relative_path.endswith(".gd"):
            self._handle_gdscript_change(relative_path)
        elif relative_path.endswith(".tscn"):
            self._handle_scene_change(relative_path)

    def _handle_gdscript_change(self, relative_path):
        """Maneja cambios en archivos GDScript."""
        print(f"🔄 Script modificado: {relative_path}")

        # Forzar hot-reload en Godot
        success = self.controller.hot_reload_scene(relative_path)

        # Notificar a EventBus
        self.watcher.notify_event_bus(
            "FILE_CHANGED",
            relative_path,
            {"type": "gdscript", "action": "hot_reload", "success": success}
        )

    def _handle_scene_change(self, relative_path):
        """Maneja cambios en escenas .tscn."""
        print(f"🎬 Escena modificada: {relative_path}")

        # Forzar hot-reload en Godot
        success = self.controller.hot_reload_scene(relative_path)

        # Notificar a EventBus
        self.watcher.notify_event_bus(
            "SCENE_CHANGED",
            relative_path,
            {"type": "scene", "action": "hot_reload", "success": success}
        )

    def on_deleted(self, event):
        """Evento cuando un archivo es eliminado."""
        if not event.is_directory:
            relative_path = os.path.relpath(event.src_path, self.watcher.project_path)
            print(f"🗑️ Archivo eliminado: {relative_path}")
            self.watcher.notify_event_bus(
                "FILE_DELETED",
                relative_path,
                {"type": "file_deleted"}
            )

if __name__ == "__main__":
    # Ejemplo de uso
    print("🚀 Iniciando Godot File Watcher...")

    # Verificar que Godot esté instalado
    controller = GodotController()

    # Iniciar watcher
    watcher = GodotFileWatcher(project_path="godot_game/", controller=controller)
    watcher.start()

    try:
        # Mantener el watcher corriendo
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo Godot File Watcher...")
        watcher.stop()
        print("✅ Godot File Watcher detenido correctamente")