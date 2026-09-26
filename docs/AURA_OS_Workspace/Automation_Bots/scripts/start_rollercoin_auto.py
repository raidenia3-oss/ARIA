import subprocess, sys, os, time, json, urllib.request

print("=" * 50)
print("ROLLERCOIN BOT - INICIO AUTOMATICO")
print("Solo la primera vez: iniciar sesion manualmente")
print("=" * 50)

restarts = 0
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


def send_alert(message: str):
    if not WEBHOOK:
        return
    try:
        data = json.dumps({"content": message}).encode()
        req = urllib.request.Request(
            WEBHOOK, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as _:
            pass
    except Exception as e:
        print(f"Error enviando alerta: {e}")


while True:
    start = time.time()
    result = subprocess.run(
        [
            sys.executable,
            "AME_Core/rollercoin/main_v2.py",
        ],
        cwd=r"C:\Users\User\Downloads\AURA",
    )
    elapsed = time.time() - start

    if result.returncode == 0:
        print("Bot terminado correctamente")
        break

    restarts += 1
    if restarts > 5:
        print("Demasiados reinicios - deteniendo")
        break

    dom_crash = elapsed < 2.0
    reason = "DOM crash sospechoso" if dom_crash else f"error code {result.returncode}"

    if restarts >= 3 or dom_crash:
        send_alert(
            f"@here RollerCoin bot fallo (intento {restarts}).\nRazon: {reason}\nTiempo: {elapsed:.1f}s"
        )

    print(f"Reiniciando en 30s... (intento {restarts})")
    time.sleep(30)
