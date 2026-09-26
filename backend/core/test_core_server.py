#!/usr/bin/env python3
"""Servidor de prueba para validar endpoints del Chunk 1."""
import sys, logging
from pathlib import Path
APP_DIR = Path("AURA_APP").resolve()
sys.path.insert(0, str(APP_DIR.parent))
sys.path.insert(0, str(APP_DIR))
_project_backend = str(APP_DIR.parent / "backend")
if _project_backend not in sys.path:
    sys.path.insert(0, _project_backend)
logging.basicConfig(level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.core_routes import router as core_router
app = FastAPI(title="AURA OS Core Test")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(core_router)
print("App lista con core_router")
