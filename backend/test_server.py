"""
Script de prueba para validar el núcleo básico de AURA OS.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from backend.api.core_routes import router as core_router


app = FastAPI(
    title="AURA OS Test",
    description="Prueba del núcleo básico de AURA OS",
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
        "message": "AURA OS Test está en funcionamiento"
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Iniciando servidor de prueba AURA OS...")
    uvicorn.run("test_server:app", host="0.0.0.0", port=8000, reload=True)