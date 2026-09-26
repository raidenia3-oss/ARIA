# AURA AI Engine - Backend principal
# Puerto: 8765

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psutil
import logging

from .model_manager import ModelManager

logger = logging.getLogger("AURA.backend")
app = FastAPI(title="AURA AI Engine")

# ModelManager carga config.json por defecto
manager = ModelManager(config_path="backend/config.json")


class SwapModelRequest(BaseModel):
    ruta_gguf: str


@app.get("/api/status")
def api_status():
    # Estado actual del sistema y modelo activo
    ram = psutil.virtual_memory()
    return JSONResponse(
        {
            "status": "ok",
            "modelo_activo": manager.get_active_model(),
            "ram_uso": ram.percent,
            "vram_uso": 0.0,
        }
    )


@app.post("/api/swap-model")
async def api_swap_model(req: SwapModelRequest):
    # Descarga el modelo actual y carga el nuevo de forma asíncrona.
    try:
        status = await manager.load_model_async(req.ruta_gguf)
        return JSONResponse(
            {
                "status": "ok",
                **status,
            }
        )
    except MemoryError as exc:
        logger.error("OOM swap-model: %s", exc)
        raise HTTPException(status_code=507, detail="Memoria insuficiente")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Modelo no encontrado")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Fallo en swap-model")
        raise HTTPException(status_code=500, detail=str(exc))


# Para ejecutar: uvicorn server:app --host 0.0.0.0 --port 8765
