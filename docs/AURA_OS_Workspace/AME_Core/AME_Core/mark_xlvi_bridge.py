"""
Bridge entre AURA y Mark-XLVI (control visual de PC por IA).
Permite automatizacion visual cuando Playwright falla.
"""

import os, sys, json, asyncio, subprocess

MARK_XLVI_REPO = "https://github.com/FatihMakes/Mark-XLVI"


class MarkXLVIBridge:
    def __init__(self):
        self.installed = self._check_installed()
        self.running = False

    def _check_installed(self) -> bool:
        mark_dir = os.path.expanduser("~/Mark-XLVI")
        return os.path.exists(mark_dir)

    def install(self) -> bool:
        if self.installed:
            print("Mark-XLVI ya instalado")
            return True

        print("Instalando Mark-XLVI...")
        try:
            result = subprocess.run(
                ["git", "clone", MARK_XLVI_REPO, os.path.expanduser("~/Mark-XLVI")],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"Error clonando: {result.stderr}")
                return False

            req_file = os.path.expanduser("~/Mark-XLVI/requirements.txt")
            if os.path.exists(req_file):
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])
            self.installed = True
            print("Mark-XLVI instalado correctamente")
            return True
        except Exception as e:
            print(f"Error instalando Mark-XLVI: {e}")
            return False

    async def execute_task(self, task: str) -> str:
        if not self.installed:
            if not self.install():
                return "Mark-XLVI no disponible"

        mark_dir = os.path.expanduser("~/Mark-XLVI")
        task_file = os.path.join(mark_dir, "aura_task.json")
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(
                {"task": task, "source": "AURA", "timestamp": asyncio.get_event_loop().time()}, f
            )

        try:
            result = subprocess.run(
                [sys.executable, "main.py", "--task", task],
                cwd=mark_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.stdout or result.stderr or "Tarea ejecutada"
        except subprocess.TimeoutExpired:
            return "Tarea tardo demasiado"
        except Exception as e:
            return f"Error: {e}"

    async def control_rollercoin_visual(self) -> bool:
        task = """
1. Abre Chrome si no esta abierto
2. Navega a https://rollercoin.com/game/games
3. Busca botones que digan 'Play' y haz click en ellos
4. Cuando aparezca una pantalla de juego,
   haz clicks en el centro de la pantalla
5. Cuando el juego termine, vuelve a /game/games
6. Repite con el siguiente juego disponible
"""
        result = await self.execute_task(task)
        return "error" not in result.lower()


async def listen_for_mark_tasks(ws_url="ws://localhost:8765"):
    import websockets

    bridge = MarkXLVIBridge()

    async with websockets.connect(ws_url) as ws:
        await ws.send(
            json.dumps(
                {
                    "node": "MARK_XLVI",
                    "event": "ONLINE",
                    "payload": {
                        "installed": bridge.installed,
                        "capabilities": [
                            "computer_control",
                            "visual_automation",
                            "rollercoin_backup",
                        ],
                    },
                }
            )
        )

        async for msg in ws:
            data = json.loads(msg)
            if data.get("event") == "MARK_TASK":
                task = data.get("payload", {}).get("task", "")
                if task:
                    result = await bridge.execute_task(task)
                    await ws.send(
                        json.dumps(
                            {
                                "node": "MARK_XLVI",
                                "event": "TASK_RESULT",
                                "payload": {"result": result},
                            }
                        )
                    )


if __name__ == "__main__":
    bridge = MarkXLVIBridge()
    bridge.install()
    print("Mark-XLVI Bridge listo")
    asyncio.run(listen_for_mark_tasks())
