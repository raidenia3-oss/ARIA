#!/usr/bin/env python3
"""
Script maestro de build — un solo comando para todo.
Uso: python scripts/build_pipeline.py [comando]
Comandos: status, build, build-release, quick, fix, open
"""

import sys, os, json, asyncio, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime

def print_header(title):
    print(f"\n{'='*50}")
    print(f"  {title}  {datetime.now().strftime('%H:%M:%S')}")
    print('='*50)

def run_status():
    from scripts.android_studio_controller import AndroidStudioController
    print_header("ESTADO DEL ENTORNO BUILD")
    as_ctrl = AndroidStudioController()
    s = as_ctrl.status()
    for k, v in s.items():
        icon = "✅" if v and v != "No encontrado" else "❌"
        print(f"  {icon} {k}: {v}")
    # Verificar output/
    apks = glob.glob("output/*.apk")
    if apks:
        print(f"\n  📦 APKs en output/: {len(apks)}")
        latest = max(apks, key=os.path.getmtime)
        size = os.path.getsize(latest) // (1024*1024)
        print(f"     Último: {os.path.basename(latest)} ({size}MB)")

def run_build(mode="debug"):
    from scripts.android_studio_controller import AndroidStudioController
    as_ctrl = AndroidStudioController()
    as_ctrl.fix_common_issues()
    apk = as_ctrl.build_apk(release=(mode=="release"), sync_first=True)
    if apk:
        print(f"\n🎉 Build exitoso! APK: {apk}")
        s = as_ctrl.status()
        if s.get("devices_connected", 0) > 0:
            as_ctrl.install_apk(apk)
        return 0
    print("\n❌ Build falló")
    return 1

def run_quick_build():
    from scripts.android_studio_controller import AndroidStudioController
    as_ctrl = AndroidStudioController()
    as_ctrl.fix_common_issues()
    apk = as_ctrl.build_apk(sync_first=True)
    if apk:
        s = as_ctrl.status()
        if s.get("devices_connected", 0) > 0:
            as_ctrl.install_apk(apk)
        else:
            try:
                asyncio.run(as_ctrl.send_apk_wireless(apk))
            except Exception as e:
                print(f"Transferencia wireless: {e}")
                print(f"APK listo en: {apk}")

def run_fix():
    from scripts.android_studio_controller import AndroidStudioController
    AndroidStudioController().fix_common_issues()

def run_open():
    from scripts.android_studio_controller import AndroidStudioController
    AndroidStudioController().open_project()

if __name__ == "__main__":
    commands = {
        "status": run_status,
        "build": lambda: run_build("debug"),
        "build-release": lambda: run_build("release"),
        "quick": run_quick_build,
        "fix": run_fix,
        "open": run_open,
    }
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fn = commands.get(cmd)
    if fn:
        sys.exit(fn())
    print(f"Uso: python {sys.argv[0]} [{'|'.join(commands.keys())}]")