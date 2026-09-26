"""FastAPI App — ARIA v4.0"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ARIA v4.0", version="4.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/aria/chat")
async def chat(message: str):
    from AURA_APP.backend.api.routes.chat import chat_route
    return await chat_route(message)

@app.get("/api/aria/usb/status")
async def usb_status():
    from AURA_APP.backend.api.routes.usb import usb_status_route
    return await usb_status_route()

@app.post("/api/aria/usb/expand")
async def usb_expand():
    from AURA_APP.backend.api.routes.usb import usb_expand_route
    return await usb_expand_route()

@app.post("/api/aria/auto")
async def aria_auto(message: str):
    from AURA_APP.backend.logic.aria_adaptive_engine import AriaAdaptiveEngine
    engine = AriaAdaptiveEngine()
    intent = await engine.identify_intent(message)
    result = await engine.execute_intelligently(intent, message)
    return result

@app.post("/api/aria/pstack/potato-mode")
async def potato_mode(request: str):
    from AURA_APP.backend.logic.pstack_orchestrator import PStackOrchestrator
    pstack = PStackOrchestrator()
    return await pstack.potato_mode(request)

@app.get("/api/aria/pstack/blast-radius/{change}")
async def blast_radius(change: str):
    from AURA_APP.backend.logic.pstack_orchestrator import PStackOrchestrator
    pstack = PStackOrchestrator()
    return await pstack.blast_radius(change)

@app.get("/api/system/health")
async def health():
    return {"status": "healthy", "version": "4.0.0"}
