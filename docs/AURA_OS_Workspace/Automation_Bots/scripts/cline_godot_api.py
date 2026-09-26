import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scripts.godot_controller import GodotController
from scripts.godot_scene_builder import SceneBuilder

class ClineGodotAPI:
    """
    Cline usa esta API para controlar Godot completamente.
    
    USO DESDE TERMINAL:
    python scripts/cline_godot_api.py --status
    python scripts/cline_godot_api.py --run
    python scripts/cline_godot_api.py --editor
    python scripts/cline_godot_api.py --build-scenes
    python scripts/cline_godot_api.py --validate scripts/Enemy.gd
    python scripts/cline_godot_api.py --logs
    python scripts/cline_godot_api.py --headless
    python scripts/cline_godot_api.py --export-apk
    """

    def __init__(self, project_path=None, godot_path=None, verbose: bool = False):
        self.verbose = bool(verbose)
        self.ctrl = GodotController(project_path=project_path, godot_path=godot_path, verbose=self.verbose)
        self.builder = SceneBuilder(self.ctrl.project_path)

    # ── ESTADO ──────────────────────────────────────────────

    def status(self):
        s = self.ctrl.status()
        print("\n=== CLINE → GODOT STATUS ===")
        print(f"Godot instalado : {'✅ ' + s['godot_path'] if s['godot_found'] else '❌ No encontrado — descarga: https://godotengine.org/download/'}")
        print(f"Proyecto Godot  : {'✅ ' + s['project_path'] if s['project_found'] else '❌ No encontrado'}")

        # Verificar escenas
        scenes_path = os.path.join(self.ctrl.project_path, "scenes")
        scenes = []
        if os.path.exists(scenes_path):
            scenes = [f for f in os.listdir(scenes_path)
                      if f.endswith(".tscn")]
        print(f"Escenas .tscn   : {len(scenes)} → {', '.join(scenes) or 'ninguna'}")

        # Verificar scripts
        scripts_path = os.path.join(self.ctrl.project_path, "scripts")
        scripts = []
        if os.path.exists(scripts_path):
            scripts = [f for f in os.listdir(scripts_path)
                       if f.endswith(".gd")]
        print(f"Scripts .gd     : {len(scripts)} → {', '.join(scripts) or 'ninguno'}")
        print()
        return s

    # ── CONTROL DEL JUEGO ───────────────────────────────────

    def run(self):
        print("🎮 Iniciando juego...")
        return self.ctrl.run_game()

    def editor(self):
        print("🖥️  Abriendo editor Godot...")
        return self.ctrl.run_editor()

    def headless(self):
        print("⚙️  Corriendo en modo headless...")
        out, err = self.ctrl.run_headless()
        print("OUTPUT:", out or "(vacío)")
        if err:
            print("ERRORS:", err)
        return out, err

    def logs(self, lines=30):
        log_lines = self.ctrl.get_logs(lines)
        print(f"\n=== ÚLTIMOS {lines} LOGS DE GODOT ===")
        for line in log_lines:
            print(line.rstrip())

    # ── ESCENAS ─────────────────────────────────────────────

    def build_scenes(self):
        print("🏗️  Construyendo escenas desde código...")
        self.builder.build_all()

    # ── VALIDACIÓN ──────────────────────────────────────────

    def validate(self, script_path):
        print(f"🔍 Validando: {script_path}")
        ok, errors = self.ctrl.validate_script(script_path)
        if ok:
            print("✅ Script válido, sin errores")
        else:
            print(f"❌ {len(errors)} error(es):")
            for e in errors:
                print(f"   {e}")
        return ok, errors

    # ── EXPORT APK ──────────────────────────────────────────

    def export_apk(self):
        print("📦 Exportando APK de Android...")
        export_presets = os.path.join(
            self.ctrl.project_path, "export_presets.cfg"
        )
        if not os.path.exists(export_presets):
            print("⚠️  No existe export_presets.cfg")
            print("   Ábrelo en Godot: Proyecto → Exportar → Añadir Android")
            print("   Luego vuelve a correr --export-apk")
            return None

        os.makedirs("output", exist_ok=True)
        result = os.system(
            f'"{self.ctrl.godot_path}" --headless '
            f'--path "{os.path.abspath(self.ctrl.project_path)}" '
            f'--export-debug "Android" '
            f'"{os.path.abspath("output/aura_ame.apk")}"'
        )
        if result == 0 and os.path.exists("output/aura_ame.apk"):
            size = os.path.getsize("output/aura_ame.apk") // 1024
            print(f"✅ APK generado: output/aura_ame.apk ({size} KB)")
            return "output/aura_ame.apk"
        else:
            print("❌ Export falló. Verifica que tienes las")
            print("   Android Export Templates instaladas en Godot.")
            return None

    # ── PIPELINE COMPLETO ───────────────────────────────────

    def full_check(self):
        """Cline llama esto para verificar todo el estado"""
        print("\n" + "="*40)
        print("PIPELINE COMPLETO CLINE → GODOT")
        print("="*40)
        self.status()

        # Validar todos los scripts
        scripts_path = os.path.join(self.ctrl.project_path, "scripts")
        if os.path.exists(scripts_path):
            all_ok = True
            for f in os.listdir(scripts_path):
                if f.endswith(".gd"):
                    ok, _ = self.validate(
                        os.path.join(scripts_path, f)
                    )
                    if not ok:
                        all_ok = False
            print(f"\nScripts: {'✅ Todos válidos' if all_ok else '❌ Hay errores'}")
        print("="*40 + "\n")


# ── ENTRY POINT CLI ─────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    project_path = None
    godot_path = None
    verbose = False

    if "--project-path" in args:
        idx = args.index("--project-path")
        if idx + 1 < len(args):
            project_path = args[idx + 1]
    if "--godot-path" in args:
        idx = args.index("--godot-path")
        if idx + 1 < len(args):
            godot_path = args[idx + 1]
    if "--verbose" in args:
        verbose = True

    # If project path not provided, try environment variables (AURA_GODOT_PROJECT_PATH then GODOT_PROJECT_PATH)
    if not project_path:
        project_path = os.getenv('AURA_GODOT_PROJECT_PATH') or os.getenv('GODOT_PROJECT_PATH')

    api = ClineGodotAPI(project_path=project_path, godot_path=godot_path, verbose=verbose)

    if not args or "--status" in args or "--verify-game-state" in args or "--get-project-info" in args or "--check-requirements" in args:
        api.status()
    if "--run" in args or "--run-game" in args:
        api.run()
    if "--editor" in args or "--start-debug-server" in args:
        api.editor()
    if "--headless" in args:
        api.headless()
    if "--logs" in args or "--get-errors" in args:
        api.logs()
    if "--build-scenes" in args or "--create-test-scenes" in args:
        api.build_scenes()
    if "--validate" in args:
        idx = args.index("--validate")
        if idx + 1 < len(args):
            api.validate(args[idx + 1])
    if "--export-apk" in args or "--export-project" in args:
        api.export_apk()
    if "--full-check" in args:
        api.full_check()
    if "--run-test-pipeline" in args:
        api.full_check()
    if "--get-godot-commands" in args:
        print("Supported commands: --status, --run, --editor, --headless, --logs, --build-scenes, --validate <path>, --export-apk, --full-check, --project-path <path>, --godot-path <path>")
    if "--get-export-status" in args:
        print(f"Project path: {api.ctrl.project_path}\nGodot path: {api.ctrl.godot_path}")
    if "--clean-export-dir" in args:
        import shutil
        output_dir = "output"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            print(f"✅ Export directory cleaned: {output_dir}")
        else:
            print(f"No hay directorio de exportación para limpiar: {output_dir}")
