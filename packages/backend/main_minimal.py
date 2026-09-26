"""AURA Backend - Minimal Windows Entrypoint
No requiere dependencias pesadas como selenium/mediapipe/opencv.
Sirve /health, /api/chat y /api/system/status.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import time
import os

app = FastAPI(title="AURA OS Minimal", version="1.0.0")

class ChatRequest(BaseModel):
    message: str

@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "mode": "windows-native", "timestamp": time.time()})

@app.get("/api/system/status")
def system_status():
    return JSONResponse({
        "backend": "running",
        "redis": "not configured",
        "mode": "windows-native",
        "path": os.getcwd(),
    })

@app.post("/api/chat")
def chat(req: ChatRequest):
    return JSONResponse({
        "response": f"[AURA minimal] Recibido: {req.message}",
        "timestamp": time.time(),
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
