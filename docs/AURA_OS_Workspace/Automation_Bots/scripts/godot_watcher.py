from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scripts.godot_controller import GodotController

class GodotWatcher(FileSystemEventHandler):

    def __init__(self, project_path):
        self.ctrl = GodotController()
        self.project_path = project_path
        self.last_reload = {}  # evitar doble-reload

    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        ext = os.path.splitext(path)[1]

        # Evitar reloads duplicados en <1s
        now = time.time()
        if path in self.last_reload:
            if now - self.last_reload[path] < 1.0:
                return
        self.last_reload[path] = now

        if ext == ".gd":
            print(f"\n🔄 Script modificado: {os.path.basename(path)}")
            ok, errors = self.ctrl.validate_script(path)
            if ok:
                print(f"   ✅ Sin errores")
                self.ctrl.hot_reload(path)
            else:
                print(f"   ❌ Errores encontrados:")
                for e in errors:
                    print(f"      {e}")

        elif ext == ".tscn":
            print(f"\n🎬 Escena modificada: {os.path.basename(path)}")
            self.ctrl.hot_reload(path)
            print(f"   ✅ Hot-reload enviado")

        elif ext == ".py" and "aura" in path.lower():
            print(f"\n🐍 AURA Core modificado: {os.path.basename(path)}")
            print(f"   ℹ️  Reinicia start_aura.py para aplicar cambios")

    def start(self):
        observer = Observer()
        observer.schedule(self, self.project_path, recursive=True)
        observer.start()
        print(f"👁️  Vigilando: {self.project_path}")
        print(f"    Ctrl+C para detener\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

if __name__ == "__main__":
    ctrl = GodotController()
    watcher = GodotWatcher(ctrl.project_path)
    watcher.start()