"""
Self-Mutation Core — Sistema de Auto-Mutacion de Codigo
=======================================================
Contiene:
  - SelfMutationEngine: Validacion AST, escritura segura y recarga en caliente
  - Funciones helper: analyze_modification_prompt, safe_write_extension, hot_reload_module
"""

import ast
import sys
import os
import importlib
import logging
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)
MUTATION_LOG: List[Dict] = []


class SelfMutationEngine:
    """Motor de auto-mutacion: validacion AST, escritura segura, hot-reload."""

    def __init__(self, modules_root: str = "AURA_Core/modules"):
        self.modules_root = modules_root
        os.makedirs(self.modules_root, exist_ok=True)
        if self.modules_root not in sys.path:
            sys.path.append(self.modules_root)

    def validate_python_syntax(self, source_code: str) -> bool:
        """Analiza el codigo usando AST para asegurar que compila perfectamente."""
        try:
            ast.parse(source_code)
            return True
        except SyntaxError as e:
            logger.error(f"Error de sintaxis en codigo autogenerado: {e.msg} en linea {e.lineno}")
            return False

    def write_new_module(self, filename: str, code_content: str) -> bool:
        """Guarda el codigo de manera segura en disco tras validacion AST."""
        if not filename.endswith(".py"):
            filename += ".py"
        target_path = os.path.join(self.modules_root, filename)
        # Limpieza basica de bloques markdown que la IA pueda arrastrar
        clean_code = code_content
        if "```python" in clean_code:
            clean_code = clean_code.split("```python")[1].split("```")[0].strip()
        elif "```" in clean_code:
            clean_code = clean_code.split("```")[1].split("```")[0].strip()
        if self.validate_python_syntax(clean_code):
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(clean_code)
            logger.info(f"Modulo '{filename}' guardado en {target_path}")
            MUTATION_LOG.append({"action": "write", "path": target_path, "size": len(clean_code)})
            return True
        return False

    def hot_reload(self, module_name: str) -> Optional[object]:
        """Carga o recarga dinamicamente un modulo en memoria sin reiniciar."""
        try:
            if module_name in sys.modules:
                reloaded = importlib.reload(sys.modules[module_name])
                logger.info(f"Modulo '{module_name}' recargado en caliente.")
                MUTATION_LOG.append({"action": "reload", "module": module_name})
                return reloaded
            else:
                new_module = importlib.import_module(module_name)
                logger.info(f"Modulo nuevo '{module_name}' importado.")
                MUTATION_LOG.append({"action": "import", "module": module_name})
                return new_module
        except Exception as e:
            logger.error(f"Fallo al recargar '{module_name}': {e}")
            return None


def analyze_modification_prompt(user_prompt: str, project_map: str, model_response: str) -> Dict:
    """Analiza prompt + mapa de proyecto para determinar archivos a modificar."""
    analysis = {
        "prompt": user_prompt[:200],
        "project_files_hint": project_map[:500],
        "model_suggestion": model_response[:500],
        "files": _extract_file_targets(model_response),
    }
    logger.info(f"analyze_modification_prompt: {len(analysis['files'])} archivos detectados")
    return analysis


def _extract_file_targets(text: str) -> List[str]:
    """Extrae rutas de archivo del texto devuelto por el modelo."""
    targets = []
    prefixes = ["AURA_Core/", "AME_Core/", "core/", "Shadow-Core/", "scripts/", "Setup/"]
    for line in text.split("\n"):
        line = line.strip().strip('"').strip("'")
        if any(line.startswith(p) for p in prefixes):
            if line.endswith(".py") or line.endswith(".js") or line.endswith(".json"):
                targets.append(line)
    return targets


def safe_write_extension(file_path: str, code_content: str) -> Dict:
    """Escribe codigo en disco con validacion AST (solo .py)."""
    path = Path(file_path)
    if file_path.endswith(".py"):
        try:
            ast.parse(code_content)
        except SyntaxError as e:
            logger.error(f"SyntaxError en {file_path}: {e}")
            return {"status": "error", "path": file_path, "error": f"SyntaxError: {e}"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code_content, encoding="utf-8")
        logger.info(f"Escrito: {file_path} ({len(code_content)} chars)")
        MUTATION_LOG.append({"action": "write", "path": file_path, "size": len(code_content)})
        return {"status": "ok", "path": file_path}
    except Exception as e:
        logger.error(f"Error escribiendo {file_path}: {e}")
        return {"status": "error", "path": file_path, "error": str(e)}


def hot_reload_module(module_name: str) -> Dict:
    """Recarga un modulo en memoria via importlib.reload."""
    try:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
            logger.info(f"Hot-reload: {module_name}")
            MUTATION_LOG.append({"action": "reload", "module": module_name})
            return {"status": "ok", "module": module_name}
        return {"status": "error", "module": module_name, "error": "No importado"}
    except Exception as e:
        logger.error(f"Error recargando {module_name}: {e}")
        return {"status": "error", "module": module_name, "error": str(e)}


def get_mutation_log() -> List[Dict]:
    """Retorna la traza completa de archivos modificados por la IA."""
    return list(MUTATION_LOG)


def clear_mutation_log():
    """Limpia la traza de mutaciones."""
    MUTATION_LOG.clear()


DESIGN_KEYWORDS = [
    "configura",
    "anade funcion",
    "modifica la app",
    "crea un modulo",
    "anade",
    "nuevo",
    "refactoriza",
    "reestructura",
    "cambia",
    "implementa",
    "construye",
    "disena",
    "extiende",
]


def should_route_to_mutation(prompt: str) -> bool:
    """Determina si el prompt debe desviarse al modulo self_mutation."""
    pl = prompt.lower()
    for kw in DESIGN_KEYWORDS:
        if kw in pl:
            return True
    return False
