"""
Módulo RollerCoin para AURA
Iniciador con auto-restart.
"""

import subprocess
import sys
import time

MAX_RESTARTS = 5
RESTART_WINDOW = 3600  # 1 hora


def run():
    restarts = 0
    start_time = time.time()

    while True:
        print(f"\n🚀 Iniciando RollerCoin Module " f"(intento {restarts+1})...")

        result = subprocess.run([sys.executable, "AME_Core/rollercoin/main.py"] + sys.argv[1:])

        # Si terminó limpio (Ctrl+C), no reiniciar
        if result.returncode == 0:
            print("✅ Módulo terminado correctamente")
            break

        restarts += 1
        elapsed = time.time() - start_time

        if restarts >= MAX_RESTARTS:
            if elapsed < RESTART_WINDOW:
                print(f"❌ {MAX_RESTARTS} reinicios en " f"{elapsed:.0f}s — deteniendo")
                break
            else:
                restarts = 0
                start_time = time.time()

        wait = min(30 * restarts, 300)
        print(f"⚠️  Crash detectado. Reiniciando en {wait}s...")
        time.sleep(wait)


if __name__ == "__main__":
    run()
