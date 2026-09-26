"""
antigravity_bridge.py - Puente AURA <-> Google Antigravity 2.0
Usa Gemini 2.0 Flash (gratis) via google-genai SDK.
"""
import asyncio, json, os, sys
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("ANTIGRAVITY_API_KEY") or os.environ.get("GEMINI_API_KEY")

def _get_client():
    """Retorna cliente Gemini"""
    try:
        from google import genai
        if not API_KEY:
            print("❌ Sin API key. Corre: python scripts/antigravity_setup.py")
            sys.exit(1)
        return genai.Client(api_key=API_KEY)
    except ImportError:
        print("❌ pip install google-genai")
        sys.exit(1)

class AntigravityBridge:
    def __init__(self, aura_ws_url="ws://localhost:8765"):
        self.aura_url = aura_ws_url
        self.client = _get_client()

    def _chat(self, system: str, task: str) -> str:
        """Envía mensaje con sistema y tarea"""
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=task,
            config={"system_instruction": system}
        )
        return response.text

    async def create_aura_agent(self, task: str, context: dict = {}):
        system = (
            "Eres un agente del ecosistema AURA/AME. "
            f"CONTEXTO: {json.dumps(context, indent=2)[:500]} "
            "CAPACIDADES: Editar archivos, ejecutar Python, controlar Godot. "
            "REGLAS: Reporta en JSON. Max 2 reintentos. Nunca edites .env."
        )
        return await asyncio.to_thread(self._chat, system, task)

    async def run_godot_agent(self, task: str):
        return await self.create_aura_agent(task, {"project": "godot_game/", "version": "4.6"})

    async def listen_eventbus(self):
        try:
            import websockets
            async with websockets.connect(self.aura_url) as ws:
                print("🤖 Antigravity conectado a AURA EventBus")
                async for message in ws:
                    event = json.loads(message)
                    await self._dispatch(event, ws)
        except Exception as e:
            print(f"❌ EventBus error: {e}")

    async def _dispatch(self, event: dict, ws):
        etype = event.get("event", "")
        data = event.get("data", {})

        if etype == "GODOT_TASK":
            result = await self.run_godot_agent(data.get("task", ""))
            await ws.send(json.dumps({"node": "ANTIGRAVITY", "event": "TASK_COMPLETE", "data": {"result": str(result)[:500]}}))

        elif etype == "ANALYZE_VULN":
            result = await self.create_aura_agent(f"Analiza: {json.dumps(data)}", {"type": "security"})
            await ws.send(json.dumps({"node": "ANTIGRAVITY", "event": "ANALYSIS_COMPLETE", "data": {"result": str(result)[:500]}}))

        elif event.get("node") == "AME_TELEMETRY" and data.get("error"):
            result = await self.create_aura_agent(f"Diagnostica error AME: {data.get('error')}")
            await ws.send(json.dumps({"node": "ANTIGRAVITY", "event": "FIX_APPLIED", "data": {"result": str(result)[:500]}}))

if __name__ == "__main__":
    bridge = AntigravityBridge()
    args = sys.argv[1:]

    if "--listen" in args:
        asyncio.run(bridge.listen_eventbus())
    elif "--godot" in args:
        idx = args.index("--godot")
        task = args[idx+1] if idx+1 < len(args) else "Verifica estado del proyecto"
        print(asyncio.run(bridge.run_godot_agent(task)))
    elif "--task" in args:
        idx = args.index("--task")
        task = args[idx+1] if idx+1 < len(args) else ""
        print(asyncio.run(bridge.create_aura_agent(task)))
    else:
        print("Uso:")
        print("  python scripts/antigravity_bridge.py --listen")
        print("  python scripts/antigravity_bridge.py --godot 'crea escena HUD'")
        print("  python scripts/antigravity_bridge.py --task 'analiza logs'")