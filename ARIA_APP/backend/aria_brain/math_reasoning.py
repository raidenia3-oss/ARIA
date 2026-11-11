"""ARIA Brain — Razonamiento matemático verificable.

Integra la skill `math` (stdlib, honesta) en el flujo de razonamiento de ARIA.
Cuando el ReasoningEngine detecta una cuestión numérica, invoca la skill y trata
el resultado como hecho verificable en lugar de suposición.

Regla de honestidad: si la skill devuelve error o "no sabe", el razonamiento
lo refleja sin inventar.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class MathReasoning:
    """Adaptador entre el razonamiento de ARIA y la skill de matemáticas."""

    def __init__(self, skill_runner=None) -> None:
        """
        skill_runner: callable(name, params) -> dict. Si es None, se intenta
        importar el SkillRegistry en tiempo de ejecucion para evitar dependencias
        circulares.
        """
        self._skill_runner = skill_runner

    def _run_math(self, operacion: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._skill_runner is not None:
            return self._skill_runner("math", {"operacion": operacion, **params})
        # Fallback: importar diferido para evitar import circular
        from backend.skills.registry import SkillRegistry
        registry = SkillRegistry()
        return registry.run("math", {"operacion": operacion, **params})

    def detectar_operacion(self, texto: str) -> Optional[Dict[str, Any]]:
        """Detecta si un texto contiene una operación matemática resoluble.

        Devuelve None si no hay operación clara. Nunca adivina números que no
        estén en el texto.
        """
        t = texto.lower()

        # Patrones simples con números explícitos
        m = re.search(r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)', t)
        if m:
            return {"operacion": "suma", "a": float(m.group(1)), "b": float(m.group(2))}

        m = re.search(r'(\d+(?:\.\d+)?)\s*\-\s*(\d+(?:\.\d+)?)', t)
        if m:
            return {"operacion": "resta", "a": float(m.group(1)), "b": float(m.group(2))}

        m = re.search(r'(\d+(?:\.\d+)?)\s*\*\s*(\d+(?:\.\d+)?)', t)
        if m:
            return {"operacion": "multiplicacion", "a": float(m.group(1)), "b": float(m.group(2))}

        m = re.search(r'(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)', t)
        if m:
            return {"operacion": "division", "a": float(m.group(1)), "b": float(m.group(2))}

        m = re.search(r'(\d+)\s*!\s*', t)
        if m:
            return {"operacion": "factorial", "n": int(m.group(1))}

        m = re.search(r'raiz\s+(?:de\s+)?(\d+(?:\.\d+)?)', t)
        if m:
            return {"operacion": "raiz", "x": float(m.group(1))}

        m = re.search(r'primo\??\s*(?:es\s+)?(\d+)', t)
        if m:
            return {"operacion": "es_primo", "n": int(m.group(1))}

        m = re.search(r'fibonacci\s+(?:de\s+)?(\d+)', t)
        if m:
            return {"operacion": "fibonacci", "n": int(m.group(1))}

        m = re.search(r'mcd\s+(?:de\s+)?(\d+)\s*[y,]\s*(\d+)', t)
        if m:
            return {"operacion": "mcd", "a": int(m.group(1)), "b": int(m.group(2))}

        m = re.search(r'mcm\s+(?:de\s+)?(\d+)\s*[y,]\s*(\d+)', t)
        if m:
            return {"operacion": "mcm", "a": int(m.group(1)), "b": int(m.group(2))}

        # Goldbach para un par concreto
        m = re.search(r'goldbach\s+(?:de\s+)?(\d+)', t)
        if m:
            return {"operacion": "verificar_goldbach", "par": int(m.group(1))}

        return None

    async def razonar_con_matematicas(self, situation: str) -> Dict[str, Any]:
        """Intenta resolver la parte matemática de una situación.

        Devuelve un dict con:
        - "tiene_matematicas": bool
        - "operacion": str|None
        - "resultado": dict|None  (resultado de la skill math, o None)
        - "verificado": bool      (True si la skill devolvió status ok y resultado no None)
        - "honesto": str          (mensaje para el usuario si no se pudo resolver)
        """
        detectado = self.detectar_operacion(situation)
        if detectado is None:
            return {
                "tiene_matematicas": False,
                "operacion": None,
                "resultado": None,
                "verificado": False,
                "honesto": "No se detectó una operación matemática clara en el texto.",
            }

        operacion = detectado["operacion"]
        params = {k: v for k, v in detectado.items() if k != "operacion"}

        try:
            resultado = self._run_math(operacion, params)
        except Exception as exc:
            return {
                "tiene_matematicas": True,
                "operacion": operacion,
                "resultado": None,
                "verificado": False,
                "honesto": f"No se pudo ejecutar la operación '{operacion}': {exc}",
            }

        if resultado.get("status") != "ok":
            return {
                "tiene_matematicas": True,
                "operacion": operacion,
                "resultado": resultado,
                "verificado": False,
                "honesto": resultado.get("error", f"Error en operación '{operacion}'"),
            }

        # El SkillRegistry envuelve el resultado en la clave "result"
        inner = resultado.get("result", resultado)
        if isinstance(inner, dict) and inner.get("resultado") is None and inner.get("error"):
            return {
                "tiene_matematicas": True,
                "operacion": operacion,
                "resultado": inner,
                "verificado": False,
                "honesto": inner.get("error", f"Operación '{operacion}' no produjo resultado"),
            }

        return {
            "tiene_matematicas": True,
            "operacion": operacion,
            "resultado": inner,
            "verificado": True,
            "honesto": "Resultado verificado por la skill de matemáticas (stdlib).",
        }
