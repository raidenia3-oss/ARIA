"""
Local Router — Puente de Inferencia Local (LM Studio + FreeBuff CLI)
====================================================================
Contiene:
  - LMStudioLocalRouter: Cliente para LM Studio (API compatible OpenAI, puerto 1234)
  - LocalRouter: Router completo con LM Studio + delegacion a freebuff

LM Studio corre en http://127.0.0.1:1234/v1 (formato OpenAI).
"""

import json, asyncio, logging, subprocess, sys, requests
from typing import Optional, Dict, List
from pathlib import Path
import httpx

# MAX MODE: Alcance inmutable del proyecto
PROJECT_SCOPE_FILE = Path(__file__).resolve().parents[2] / "project_scope.json"
MAX_MODE_PROMPT_INJECTION = (
    "\n\n[MAX_MODE]\n"
    "Reglas inamovibles del imperio:\n{rules}\n"
    "===\n"
    "INSTRUCCIONES:\n"
    "- Valida que tu salida cumpla CADA regla listada arriba.\n"
    "- No generes dependencias circulares.\n"
    "- No crees archivos innecesarios ni scripts extra.\n"
    "- Si una petición viola el alcance, responde: 'MAX_MODE_BLOCKED'.\n"
    "- Solo responde con el código o texto requerido, sin explicaciones,\n"
    "  sin comentarios adicionales y sin aulas.\n"
)
MAX_MODE_CLOSING_INJECTION = (
    "\n===\n[REVALIDACIÓN MAX_MODE]\n"
    "Revisa rápidamente tu respuesta contra las reglas listadas. "
    "Si detectas desviación, corrígela ahora. "
    "Si no es corregible, responde: 'MAX_MODE_BLOCKED'.\n"
)

logger = logging.getLogger(__name__)
LM_STUDIO_BASE = "http://127.0.0.1:1234/v1"
LOCAL_MODEL = "local-model"
FREEBUFF_CMD = "freebuff"


class LMStudioLocalRouter:
    """Cliente para LM Studio usando formato OpenAI (puerto 1234)."""

    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1"):
        self.api_url = f"{base_url}/chat/completions"

    async def generate_code(
        self, prompt: str, system_context: str = "", max_mode: bool = False
    ) -> str:
        """
        Envia una peticion a LM Studio usando el formato oficial de OpenAI.
        LM Studio procesa el modelo que tengas cargado en la interfaz visual.
        """
        final_system = (
            system_context
            or "Eres un ingeniero de software experto. Devuelve SOLO codigo limpio de Python, sin bloques de comentarios explicativos, ni introducciones."
        )
        final_user = prompt
        if max_mode:
            rules = aplicar_max_mode(final_system)
            injection = MAX_MODE_PROMPT_INJECTION.format(rules=rules)
            final_system = final_system + injection
            final_user = final_user + MAX_MODE_CLOSING_INJECTION
        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": final_system},
                {"role": "user", "content": final_user},
            ],
            "temperature": 0.2,
            "stream": False,
        }

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.post(self.api_url, json=payload, timeout=60)
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                return f"ERROR_INFERENCIA: Codigo de estado {response.status_code}"

        except requests.exceptions.ConnectionError:
            return "ERROR_CONEXION: LM Studio esta apagado o el servidor local no esta activo en el puerto 1234."
        except Exception as e:
            return f"ERROR_INFERENCIA: {str(e)}"

    async def chat(self, prompt: str, max_mode: bool = False) -> Optional[str]:
        """Chat simple con LM Studio."""
        code = await self.generate_code(prompt, max_mode=max_mode)
        if code.startswith("ERROR"):
            return None
        return code


class LocalRouter:
    """Router de inferencia local con LM Studio + delegacion a freebuff."""

    def __init__(self):
        self._lm_studio_ok: Optional[bool] = None
        self._freebuff_cmd = self._find_freebuff()
        self._lm_router = LMStudioLocalRouter()
        if self._freebuff_cmd:
            logger.info(f"FreeBuff detectado: {self._freebuff_cmd}")
        else:
            logger.warning("FreeBuff no encontrado en PATH. Modo LM Studio-only.")

    def _find_freebuff(self) -> Optional[str]:
        """Busca el binario freebuff en el sistema."""
        for candidate in ["freebuff", "npx freebuff"]:
            try:
                r = subprocess.run(candidate.split(), capture_output=True, text=True, timeout=3)
                if r.returncode in (0, 1):
                    return candidate
            except FileNotFoundError:
                continue
        return None

    async def _check_lm_studio(self) -> bool:
        """Verifica si LM Studio responde en /v1/models."""
        if self._lm_studio_ok is not None:
            return self._lm_studio_ok
        try:
            async with httpx.AsyncClient() as c:
                resp = await c.get(f"{LM_STUDIO_BASE}/models", timeout=5)
                self._lm_studio_ok = resp.status_code == 200
        except Exception:
            self._lm_studio_ok = False
        return self._lm_studio_ok

    async def generate_code(self, prompt: str, system_context: str = "") -> str:
        """Delegar a LMStudioLocalRouter.generate_code."""
        return await self._lm_router.generate_code(prompt, system_context)

    async def chat(self, prompt: str) -> Optional[str]:
        """Chat simple con LM Studio."""
        if not await self._check_lm_studio():
            logger.error("LM Studio no disponible")
            return None
        return await self._lm_router.chat(prompt)

    async def freebuff_refactor(self, prompt: str, target_file: str) -> Dict:
        """Delega refactorizacion a freebuff."""
        if not self._freebuff_cmd:
            return {"status": "error", "output": "freebuff no disponible", "file": target_file}
        cmd = f'{self._freebuff_cmd} refactor "{target_file}" --prompt "{prompt}"'
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode() if stdout else ""
            err = stderr.decode() if stderr else ""
            if proc.returncode == 0:
                logger.info(f"FreeBuff refactor OK: {target_file}")
                return {"status": "ok", "output": output.strip(), "file": target_file}
            logger.error(f"FreeBuff error ({proc.returncode}): {err[:200]}")
            return {"status": "error", "output": err[:500], "file": target_file}
        except asyncio.TimeoutError:
            return {"status": "error", "output": "Timeout 120s", "file": target_file}
        except Exception as e:
            return {"status": "error", "output": str(e), "file": target_file}

    async def analyze_and_route(self, user_prompt: str, file_map: str = "") -> Dict:
        """Analiza y decide ruta: LM Studio o freebuff."""
        if not await self._check_lm_studio():
            return {"status": "error", "message": "LM Studio no disponible"}
        response = await self._lm_router.chat(user_prompt)
        return {"status": "ok", "provider": "lm_studio", "response": response, "model": LOCAL_MODEL}


def aplicar_max_mode(system_prompt: str) -> str:
    """
    Lee project_scope.json y devuelve el listado de reglas
    que seinyectarán en el prompt del sistema.
    """
    try:
        if PROJECT_SCOPE_FILE.exists():
            data = json.loads(PROJECT_SCOPE_FILE.read_text(encoding="utf-8"))
            rules = data.get("rules", [])
            if not isinstance(rules, list):
                rules = [str(rules)]
            return "\n".join(f"- {r}" for r in rules)
    except Exception:
        pass
    return "- Estilo visual: Carmesí\n- Sin dependencias circulares\n- Puerto: 8765\n- No generar archivos innecesarios"


async def test_connection() -> Dict:
    """Test rapido: verifica que LM Studio responde."""
    router = LocalRouter()
    ok = await router._check_lm_studio()
    return {
        "lm_studio_available": ok,
        "freebuff_available": router._freebuff_cmd is not None,
        "endpoint": LM_STUDIO_BASE + "/chat/completions",
        "model": LOCAL_MODEL,
    }
