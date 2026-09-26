"""
Script para depurar el inicio del servidor FastAPI.
"""

import uvicorn
from fastapi import FastAPI
from backend.core.ws_routes import router


app = FastAPI(title="AURA OS API", version="0.1.0")
app.include_router(router, prefix="/api")


if __name__ == "__main__":
    print("Iniciando servidor FastAPI...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")