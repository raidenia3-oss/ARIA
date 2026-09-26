"""BLOQUE 91 - AURA Local Autonomous Code Refactoring & Dynamic Hot-Patching Engine.

Motor 100% local de refactorización autónoma de código y hot-patching dinámico.
Complementa el Bloque 70 (autoevolución) con:
- Análisis estático con AST para detección de code smells
- Síntesis de refactorizaciones seguras (rename, extract method, simplify)
- Hot-patching dinámico en caliente (reload de módulos sin reiniciar)
- Auditoría de todos los cambios con hash y rollback

Almacenamiento: data/refactoring91/{patches, backups, logs, metrics/}
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.refactoring.models import (
    RefactoringFinding,
    RefactoringMetrics,
    RefactoringType,
    PatchProposal,
    PatchStatus,
    HotPatchRecord,
    ModuleState,
    _utcnow_iso,
    _now_ts,
)

logger = logging.getLogger("AURA.Refactoring")

DATA_DIR = Path(
    os.getenv("AURA_REFACTORING91_DIR",
              os.path.join(os.getcwd(), "data", "refactoring91"))
)
for _sub in ("patches", "backups", "logs", "metrics", "modules"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)
