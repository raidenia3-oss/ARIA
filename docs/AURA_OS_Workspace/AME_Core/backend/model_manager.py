# NOTA: Requiere VS Build Tools para compilar llama-cpp-python.
# Si no está instalado, este módulo queda como stub.

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional

try:
    from llama_cpp import Llama
except Exception:
    Llama = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AURA.model_manager")


class ModelManager:
    # Administra carga/descarga de modelos GGUF en RAM.

    def __init__(self, config_path: str = "backend/config.json"):
        # Carga límites desde config.json
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.max_vram_mb = cfg.get("max_vram_mb", 4096)
        self.max_ram_mb = cfg.get("max_ram_mb", 8192)
        self.modelos = cfg.get("modelos", [])
        self.active_model: Optional[str] = None
        self._llm = None

    def load_model(self, ruta_gguf: str) -> dict:
        # Carga el modelo GGUF solicitado en RAM.
        if Llama is None:
            raise RuntimeError(
                "llama-cpp-python no instalado. "
                "Instala VS Build Tools y pip install llama-cpp-python"
            )
        if not os.path.exists(ruta_gguf):
            raise FileNotFoundError(ruta_gguf)
        # Si hay otro modelo cargado, lo descargamos primero
        if self._llm is not None:
            self.unload_model()
        try:
            self._llm = Llama(model_path=ruta_gguf, n_ctx=2048)
            self.active_model = os.path.basename(ruta_gguf)
            logger.info("Modelo cargado: %s", self.active_model)
            return self._status()
        except Exception as exc:
            logger.error("Fallo cargando %s: %s", ruta_gguf, exc)
            raise

    async def load_model_async(self, ruta_gguf: str) -> dict:
        # Ejecuta la carga pesada fuera del event loop de FastAPI.
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.load_model, ruta_gguf)

    def unload_model(self) -> None:
        # Libera memoria del modelo actual
        self._llm = None
        self.active_model = None
        logger.info("Modelo descargado de RAM")

    def get_active_model(self) -> Optional[str]:
        # Retorna el nombre del modelo activo o None
        return self.active_model

    def _status(self) -> dict:
        # Retorna métricas simples de estado
        import psutil

        ram = psutil.virtual_memory()
        return {
            "modelo_activo": self.active_model,
            "ram_uso": ram.percent,
            "vram_uso": 0.0,
        }
