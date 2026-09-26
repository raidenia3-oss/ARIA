import subprocess, os, sys, json, time, glob

class GodotController:

    def __init__(self, project_path=None, godot_path=None, verbose: bool = False):
        self.verbose = bool(verbose)
        self.godot_path = godot_path if godot_path and os.path.exists(godot_path) else self._find_godot()
        if project_path and os.path.exists(os.path.join(project_path, "project.godot")):
            self.project_path = project_path
        else:
            self.project_path = self._find_project()

    def _find_godot(self):
        """Busca el ejecutable de Godot en el sistema"""
        # Primero: leer del .env si existe
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GODOT_PATH=") and "=" in line:
                        path = line.split("=", 1)[1].strip()
                        if os.path.exists(path):
                            return path

        candidates = [
            # Windows
            "C:/Program Files/Godot/Godot_v4*.exe",
            "C:/Program Files (x86)/Godot/Godot_v4*.exe",
            os.path.expanduser("~/Downloads/Godot*.exe"),
            os.path.expanduser("~/Desktop/Godot*.exe"),
            # Linux
            "/usr/bin/godot4",
            "/usr/local/bin/godot4",
            os.path.expanduser("~/.local/bin/godot4"),
        ]
        for pattern in candidates:
            matches = glob.glob(pattern)
            if matches:
                return matches[0]
        
        # Buscar en PATH
        for name in ["godot4", "godot", "Godot_v4"]:
            result = subprocess.run(
                ["where" if sys.platform=="win32" else "which", name],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        return None

    def _find_project(self):
        """Busca project.godot en el filesystem.

        Para evitar que Cline tarde mucho en repositorios grandes,
        primero revisa variables de entorno y rutas conocidas.
        """
        # Soporta ambas variables de entorno por compatibilidad
        env_path = os.getenv("AURA_GODOT_PROJECT_PATH") or os.getenv("GODOT_PROJECT_PATH")
        if env_path and os.path.exists(os.path.join(env_path, "project.godot")):
            if self.verbose:
                print(f"[godot_controller] Using project path from env: {env_path}")
            return env_path

        candidates = [
            os.path.join(os.getcwd(), "godot_game"),
            os.path.join(os.getcwd(), "AURA", "godot_game"),
            os.path.join(os.getcwd(), "game"),
            os.path.join(os.getcwd(), "project"),
        ]
        for path in candidates:
            if os.path.exists(os.path.join(path, "project.godot")):
                return path

        # Search with a shallow walk and prune large folders to avoid repo-wide scans.
        excluded = {".git", "node_modules", "env", ".venv", "venv", "dist", "android", "build", "out", "__pycache__"}
        max_depth = 3
        start_depth = os.path.abspath('.').count(os.sep)
        for root, dirs, files in os.walk('.', topdown=True):
            # prune excluded dirs
            dirs[:] = [d for d in dirs if d not in excluded]
            # enforce shallow depth
            cur_depth = os.path.abspath(root).count(os.sep) - start_depth
            if cur_depth > max_depth:
                dirs[:] = []
                continue
            if 'project.godot' in files:
                found = os.path.abspath(root)
                if self.verbose:
                    print(f"[godot_controller] Found project.godot at: {found}")
                return found

        return "godot_game"

    def status(self):
        """Retorna estado completo"""
        return {
            "godot_found": self.godot_path is not None,
            "godot_path": self.godot_path,
            "project_found": os.path.exists(
                os.path.join(self.project_path, "project.godot")
            ),
            "project_path": self.project_path,
        }

    def run_editor(self):
        """Abre el editor de Godot"""
        if not self.godot_path:
            print("❌ Godot no encontrado.")
            print("📥 Descárgalo gratis: https://godotengine.org/download/")
            return False
        subprocess.Popen([
            self.godot_path, "--editor",
            "--path", os.path.abspath(self.project_path)
        ])
        print(f"✅ Godot editor abierto: {self.project_path}")
        return True

    def run_game(self, scene=None):
        """Corre el juego"""
        cmd = [self.godot_path, "--path", os.path.abspath(self.project_path)]
        if scene:
            cmd.append(scene)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        print(f"🎮 Juego corriendo (PID {proc.pid})")
        return proc

    def run_headless(self, script="scripts/headless_test.gd"):
        """Corre Godot sin ventana para tests"""
        result = subprocess.run([
            self.godot_path, "--headless",
            "--path", os.path.abspath(self.project_path),
            "--script", script
        ], capture_output=True, text=True, timeout=30)
        return result.stdout, result.stderr

    def get_logs(self, lines=50):
        """Lee los últimos logs de Godot"""
        log_paths = [
            os.path.expanduser(
                "~/.local/share/godot/app_userdata/AURA/logs/godot.log"
            ),
            os.path.expandvars(
                r"%APPDATA%\Godot\app_userdata\AURA\logs\godot.log"
            ),
        ]
        for path in log_paths:
            if os.path.exists(path):
                with open(path) as f:
                    return f.readlines()[-lines:]
        return ["No se encontraron logs aún"]

    def hot_reload(self, filepath):
        """Fuerza recarga de un archivo en Godot"""
        os.utime(filepath, None)
        print(f"🔄 Hot-reload: {filepath}")

    def validate_script(self, filepath):
        """Valida sintaxis de un GDScript"""
        if not self.godot_path:
            return False, ["Godot no instalado. Descarga: https://godotengine.org/download/"]
        result = subprocess.run([
            self.godot_path, "--headless",
            "--path", os.path.abspath(self.project_path),
            "--check-only", filepath
        ], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, []
        errors = [l for l in result.stderr.splitlines() if "ERROR" in l]
        return False, errors

if __name__ == "__main__":
    import sys
    project_path = None
    godot_path = None
    if "--project-path" in sys.argv:
        idx = sys.argv.index("--project-path")
        if idx + 1 < len(sys.argv):
            project_path = sys.argv[idx + 1]
    if "--godot-path" in sys.argv:
        idx = sys.argv.index("--godot-path")
        if idx + 1 < len(sys.argv):
            godot_path = sys.argv[idx + 1]

    ctrl = GodotController(project_path=project_path, godot_path=godot_path)
    s = ctrl.status()
    print("=== GODOT STATUS ===")
    print(f"Godot:   {'✅ ' + s['godot_path'] if s['godot_found'] else '❌ No encontrado'}")
    print(f"Proyecto:{'✅ ' + s['project_path'] if s['project_found'] else '❌ No encontrado'}")

    if "--run" in sys.argv:      ctrl.run_game()
    if "--editor" in sys.argv:   ctrl.run_editor()
    if "--headless" in sys.argv: print(ctrl.run_headless())
    if "--logs" in sys.argv:     print('\n'.join(ctrl.get_logs()))