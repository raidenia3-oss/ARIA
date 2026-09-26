"""
Script principal para iniciar el servidor FastAPI de AURA OS.
"""
from fastapi import FastAPI
from backend.api.core_routes import router as core_router
from backend.api.core_routes import ws_router


app = FastAPI(title="AURA OS API", version="0.1.0")
app.include_router(core_router)
app.include_router(ws_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)