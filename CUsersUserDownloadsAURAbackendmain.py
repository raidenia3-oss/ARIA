
URA OS — Chunk 1: Main Application.

Punto de entrada principal de la aplicación FastAPI.


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from backend.api.core_routes import router as core_router

app = FastAPI(
    title="AURA OS",
    description="Sistema operativo de IA modular",
    version="1.0.0",
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Incluir rutas
app.include_router(core_router, prefix="/")

@app.get("/health")
def health_check() -> dict:
    """Verifica que el sistema esté funcionando correctamente."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "message": "AURA OS está en funcionamiento"
    }

@app.get("/")
def root() -> dict:
    """Página principal de la API."""
    return {
        "message": "Bienvenido a AURA OS",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Iniciando servidor AURA OS...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
