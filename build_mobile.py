#!/usr/bin/env python3
import subprocess
import sys
import shutil

def build_apk():
    print("[BUILD] Compilando AME.apk...")
    flet_cmd = shutil.which("flet")
    if flet_cmd:
        cmd = [flet_cmd, "build", "apk", "--output", "dist", "--artifact", "ame", "mobile_client"]
    else:
        cmd = [sys.executable, "-m", "flet", "build", "apk", "--output", "dist", "--artifact", "ame", "mobile_client"]
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("[SUCCESS] dist/ame.apk generado")
        print("[NEXT] Instala en celular: adb install dist/ame.apk")
    else:
        print("[ERROR] Compilación fallida")
        print("[HINT] Requiere Flutter SDK + flet: pip install flet")
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(build_apk())
