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


# --- Expresiones aritmeticas completas (precedencia, negativos, parentesis, ^, %) ---
# Antes, "2 + 3 * 4" daba 5 y "-3 + 5" daba 8 marcados como verificados. Ahora se evalua la
# expresion ENTERA con el arbol de Python (solo numeros y + - * / ^ %), exacta con Fraction.
import ast as _ast
from fractions import Fraction as _Fr

_EXPR = re.compile(r'(?<![\w.])[-+(]*\s*\d[\d\s.,+\-*/^%()x×÷]*\d\s*\)*')
_OPS = {_ast.Add: lambda a, b: a + b, _ast.Sub: lambda a, b: a - b, _ast.Mult: lambda a, b: a * b,
        _ast.Div: lambda a, b: a / b, _ast.Mod: lambda a, b: a % b}


def _eval_nodo(n):
    if isinstance(n, _ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return _Fr(str(n.value))
    if isinstance(n, _ast.UnaryOp) and isinstance(n.op, (_ast.USub, _ast.UAdd)):
        v = _eval_nodo(n.operand)
        return -v if isinstance(n.op, _ast.USub) else v
    if isinstance(n, _ast.BinOp):
        a, b = _eval_nodo(n.left), _eval_nodo(n.right)
        if isinstance(n.op, _ast.Pow):
            if b.denominator != 1 or abs(b) > 1000 or abs(a) > 10 ** 12:
                raise ValueError("potencia demasiado grande o no entera")
            return a ** int(b)
        if type(n.op) in _OPS:
            if isinstance(n.op, (_ast.Div, _ast.Mod)) and b == 0:
                raise ZeroDivisionError("division entre cero")
            return _OPS[type(n.op)](a, b)
    raise ValueError("expresion no soportada")


def _formato(v):
    if v.denominator == 1:
        return int(v)
    f = float(v)
    return round(f, 10)


def evaluar_expresion(texto: str):
    """Devuelve (expresion_normalizada, valor) de la expresion aritmetica mas larga del texto, o None."""
    t = texto.lower().replace('×', '*').replace('÷', '/')
    mejor = None
    for m in _EXPR.finditer(t):
        cand = m.group(0).strip()
        if not re.search(r'\d\s*[-+*/^%x]\s*[-+(]*\s*\d', cand):
            continue                                   # un solo numero: no es una operacion
        antes = t[:m.start()].rstrip()
        despues = t[m.end():].lstrip()
        if re.search(r'(?:^|[^a-záéíóúñ])[a-z]\s*[*]?$', antes) or despues.startswith('='):
            continue                                   # "x + 2 = 5": ecuacion, no aritmetica pura
        c = re.sub(r'(\d),(\d{1,2})(?!\d)', r'\1.\2', cand)   # 2,5 -> 2.5
        c = re.sub(r'(?<=\d)\s*x\s*(?=\d)', '*', c).replace('^', '**')
        if mejor is None or len(c) > len(mejor):
            mejor = c
    if mejor is None:
        return None
    # equilibrar parentesis sobrantes de los bordes
    while mejor.count('(') < mejor.count(')') and mejor.endswith(')'):
        mejor = mejor[:-1].rstrip()
    while mejor.count('(') > mejor.count(')') and mejor.startswith('('):
        mejor = mejor[1:].lstrip()
    arbol = _ast.parse(mejor, mode='eval').body
    return mejor.replace('**', '^'), _eval_nodo(arbol)


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

        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%\s*de\s*(\d+(?:[.,]\d+)?)', t)
        if m:
            return {"operacion": "porcentaje", "p": m.group(1).replace(',', '.'), "x": m.group(2).replace(',', '.')}
        if re.search(r'\d\s*[-+*/^x×÷]\s*[-+(]*\s*\d', t):
            return {"operacion": "expresion", "texto": texto}

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

        m = re.search(r'raiz\s+(?:cuadrada\s+)?(?:de\s+)?(-?\d+(?:\.\d+)?)', t)
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

        if operacion in ("expresion", "porcentaje"):
            try:
                if operacion == "porcentaje":
                    expr = f'{params["p"]}% de {params["x"]}'
                    val = _Fr(params["p"]) * _Fr(params["x"]) / 100
                else:
                    r = evaluar_expresion(params["texto"])
                    if r is None:
                        return {"tiene_matematicas": False, "operacion": None, "resultado": None, "verificado": False,
                                "honesto": "No hay una operacion aritmetica completa que pueda calcular sin adivinar."}
                    expr, val = r
                res = {"status": "ok", "skill": "math", "operacion": operacion, "expresion": expr,
                       "resultado": _formato(val), "exacto": str(val), "nivel": "simple"}
                return {"tiene_matematicas": True, "operacion": operacion, "resultado": res, "verificado": True,
                        "honesto": "Calculado con la expresion completa (precedencia y signos respetados), stdlib."}
            except ZeroDivisionError:
                res = {"status": "ok", "resultado": None, "error": "division entre cero: no tiene resultado"}
                return {"tiene_matematicas": True, "operacion": operacion, "resultado": res, "verificado": False,
                        "honesto": res["error"]}
            except (ValueError, SyntaxError) as exc:
                return {"tiene_matematicas": True, "operacion": operacion, "resultado": None, "verificado": False,
                        "honesto": f"No pude calcular eso sin adivinar ({exc})."}

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
