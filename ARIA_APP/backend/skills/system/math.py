"""ARIA skill: matematicas con solo stdlib.

Honestidad contractual: si el resultado no es computable con certeza o el
problema esta abierto/no resuelto, la skill devuelve "sabido": False y nunca
inventa soluciones. Niveles: simple -> intermedio -> avanzado -> abierto.
"""
from __future__ import annotations

import math
from fractions import Fraction
from decimal import Decimal, getcontext, InvalidOperation
from typing import Any, Dict

getcontext().prec = 50

# Problemas matematicos abiertos / no resueltos conocidos (no se inventa solucion)
# Fuente: conocimiento general de matematicas. Ninguna solucion se afirma.
ABIERTOS = {
    "conjetura_de_goldbach": {
        "enunciado": "Todo par mayor que 2 es suma de dos primos.",
        "estado": "No resuelto (abierto). Verificado computacionalmente hasta "
                   "cotas muy altas, pero sin demostracion general.",
        "ejemplo_verificable": "4 = 2+2, 6 = 3+3, 8 = 3+5, 10 = 3+7 o 5+5",
    },
    "conjetura_de_los_primos_gemeos": {
        "enunciado": "Existen infinitos primos p tales que p+2 tambien es primo.",
        "estado": "No resuelto (abierto). Zhang (2013) y Maynard/Tao demostraron "
                   "cotas acotadas para brechas entre primos, pero no la conjetura.",
    },
    "hipotesis_de_riemann": {
        "enunciado": "Todos los ceros no triviales de la zeta de Riemann tienen "
                     "parte real 1/2.",
        "estado": "No resuelto (abierto, uno de los problemas del milenio).",
    },
    "p_versus_np": {
        "enunciado": "Si P es igual a NP.",
        "estado": "No resuelto (abierto, uno de los problemas del milenio).",
    },
    "conjetura_de_collatz": {
        "enunciado": "Para cualquier entero positivo n, aplicar: si par n/2, si "
                     "impar 3n+1, siempre llega a 1.",
        "estado": "No resuelto (abierto). Verificado para cotas enormes pero sin "
                   "demostracion general.",
    },
    "conjetura_de_erdos_straus": {
        "enunciado": "Para todo n >= 2, 4/n = 1/x + 1/y + 1/z con x,y,z enteros "
                     "positivos.",
        "estado": "No resuelto (abierto).",
    },
}


def _es_primo(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    r = int(math.isqrt(n))
    for i in range(3, r + 1, 2):
        if n % i == 0:
            return False
    return True


def _siguiente_primo(n: int) -> int:
    cand = n + 1
    while not _es_primo(cand):
        cand += 1
    return cand


def _descomposicion_prima(n: int) -> Dict[int, int]:
    """Devuelve {primo: exponente} de la factorizacion de n."""
    factores: Dict[int, int] = {}
    d = 2
    temp = n
    while d * d <= temp:
        while temp % d == 0:
            factores[d] = factores.get(d, 0) + 1
            temp //= d
        d += 1 if d == 2 else 2
    if temp > 1:
        factores[temp] = factores.get(temp, 0) + 1
    return factores


def _mcd(a: int, b: int) -> int:
    return math.gcd(a, b)


def _mcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b) if a and b else 0


def _verificar_goldbach(par: int) -> Dict[str, Any]:
    """Verifica la conjetura de Goldbach para un par concreto (no demuestra nada)."""
    if par <= 2 or par % 2 != 0:
        return {"valido": False,
                "motivo": "Goldbach aplica solo a pares mayores que 2."}
    pares = []
    for p in range(2, par // 2 + 1):
        q = par - p
        if _es_primo(p) and _es_primo(q):
            pares.append({"p": p, "q": q})
    return {"valido": True, "par": par, "descomposiciones": pares}


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    operacion = str(params.get("operacion", "")).strip().lower()
    if not operacion:
        return {
            "status": "error",
            "skill": "math",
            "error": "Falta 'operacion'. Ejemplos: suma, resta, multiplicacion, division, "
                     "potencia, raiz, factorial, mcd, mcm, es_primo, descomposicion_prima, "
                     "siguiente_primo, fibonacci, verificar_goldbach, problema_abierto.",
        }

    try:
        # ---------------- NIVEL SIMPLE ----------------
        if operacion == "suma":
            a = _num(params.get("a")); b = _num(params.get("b"))
            return {"status": "ok", "skill": "math", "operacion": "suma",
                    "a": a, "b": b, "resultado": a + b, "nivel": "simple"}

        if operacion == "resta":
            a = _num(params.get("a")); b = _num(params.get("b"))
            return {"status": "ok", "skill": "math", "operacion": "resta",
                    "a": a, "b": b, "resultado": a - b, "nivel": "simple"}

        if operacion == "multiplicacion":
            a = _num(params.get("a")); b = _num(params.get("b"))
            return {"status": "ok", "skill": "math", "operacion": "multiplicacion",
                    "a": a, "b": b, "resultado": a * b, "nivel": "simple"}

        if operacion == "division":
            a = _num(params.get("a")); b = _num(params.get("b"))
            if b == 0:
                return {"status": "ok", "skill": "math", "operacion": "division",
                        "a": a, "b": b, "resultado": None,
                        "error": "Division entre cero no definida", "nivel": "simple"}
            return {"status": "ok", "skill": "math", "operacion": "division",
                    "a": a, "b": b, "resultado": a / b, "nivel": "simple"}

        if operacion == "potencia":
            base = _num(params.get("base")); exp = _num(params.get("exp"))
            return {"status": "ok", "skill": "math", "operacion": "potencia",
                    "base": base, "exp": exp, "resultado": base ** exp, "nivel": "simple"}

        if operacion == "raiz":
            x = _num(params.get("x"))
            if x < 0:
                return {"status": "ok", "skill": "math", "operacion": "raiz",
                        "x": x, "resultado": None,
                        "error": "Raiz cuadrada de negativo no es real", "nivel": "simple"}
            return {"status": "ok", "skill": "math", "operacion": "raiz",
                    "x": x, "resultado": math.sqrt(x), "nivel": "simple"}

        if operacion == "factorial":
            n = _entero(params.get("n"))
            if n < 0:
                return {"status": "ok", "skill": "math", "operacion": "factorial",
                        "n": n, "resultado": None,
                        "error": "Factorial no definido para negativos", "nivel": "simple"}
            return {"status": "ok", "skill": "math", "operacion": "factorial",
                    "n": n, "resultado": math.factorial(n), "nivel": "simple"}

        # ---------------- NIVEL INTERMEDIO ----------------
        if operacion == "mcd":
            a = _entero(params.get("a")); b = _entero(params.get("b"))
            return {"status": "ok", "skill": "math", "operacion": "mcd",
                    "a": a, "b": b, "resultado": _mcd(a, b), "nivel": "intermedio"}

        if operacion == "mcm":
            a = _entero(params.get("a")); b = _entero(params.get("b"))
            return {"status": "ok", "skill": "math", "operacion": "mcm",
                    "a": a, "b": b, "resultado": _mcm(a, b), "nivel": "intermedio"}

        if operacion == "es_primo":
            n = _entero(params.get("n"))
            return {"status": "ok", "skill": "math", "operacion": "es_primo",
                    "n": n, "resultado": _es_primo(n), "nivel": "intermedio"}

        if operacion == "descomposicion_prima":
            n = _entero(params.get("n"))
            if n < 2:
                return {"status": "ok", "skill": "math", "operacion": "descomposicion_prima",
                        "n": n, "resultado": None,
                        "error": "Solo enteros >= 2", "nivel": "intermedio"}
            return {"status": "ok", "skill": "math", "operacion": "descomposicion_prima",
                    "n": n, "resultado": _descomposicion_prima(n), "nivel": "intermedio"}

        if operacion == "siguiente_primo":
            n = _entero(params.get("n"))
            return {"status": "ok", "skill": "math", "operacion": "siguiente_primo",
                    "n": n, "resultado": _siguiente_primo(n), "nivel": "intermedio"}

        if operacion == "fibonacci":
            n = _entero(params.get("n"))
            if n < 0:
                return {"status": "ok", "skill": "math", "operacion": "fibonacci",
                        "n": n, "resultado": None,
                        "error": "n debe ser >= 0", "nivel": "intermedio"}
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            return {"status": "ok", "skill": "math", "operacion": "fibonacci",
                    "n": n, "resultado": a, "nivel": "intermedio"}

        # ---------------- NIVEL AVANZADO ----------------
        if operacion == "verificar_goldbach":
            par = _entero(params.get("par"))
            return {"status": "ok", "skill": "math", "operacion": "verificar_goldbach",
                    **_verificar_goldbach(par), "nivel": "avanzado"}

        if operacion == "serie_armonica_parcial":
            n = _entero(params.get("n"))
            if n < 1:
                return {"status": "ok", "skill": "math", "operacion": "serie_armonica_parcial",
                        "n": n, "resultado": None,
                        "error": "n debe ser >= 1", "nivel": "avanzado"}
            total = Fraction(0, 1)
            for k in range(1, n + 1):
                total += Fraction(1, k)
            return {"status": "ok", "skill": "math", "operacion": "serie_armonica_parcial",
                    "n": n, "resultado_exacto": f"{total.numerator}/{total.denominator}",
                    "resultado_decimal": float(total),
                    "nota": "La serie armonica diverge (crece sin cota) cuando n -> infinito",
                    "nivel": "avanzado"}

        if operacion == "constante_e":
            n = int(params.get("terminos", 20))
            e = Fraction(0, 1)
            fact = Fraction(1, 1)
            for k in range(n):
                if k > 0:
                    fact *= k
                e += Fraction(1, 1) / fact
            return {"status": "ok", "skill": "math", "operacion": "constante_e",
                    "terminos": n, "resultado_exacto": f"{e.numerator}/{e.denominator}",
                    "resultado_decimal": float(e),
                    "nota": "e = sum(1/k!) es irracional y trascendente", "nivel": "avanzado"}

        if operacion == "numero_pi_leibniz":
            n = int(params.get("terminos", 10000))
            total = Fraction(0, 1)
            for k in range(n):
                total += Fraction((-1) ** k, 2 * k + 1)
            pi_aprox = 4 * total
            return {"status": "ok", "skill": "math", "operacion": "numero_pi_leibniz",
                    "terminos": n, "pi_aproximado": float(pi_aprox),
                    "nota": "Serie de Leibniz: pi/4 = 1 - 1/3 + 1/5 - ... converge lentamente",
                    "nivel": "avanzado"}

        # ---------------- PROBLEMAS ABIERTOS / NO RESUELTOS ----------------
        if operacion == "problema_abierto":
            nombre = str(params.get("nombre", "")).strip().lower()
            if not nombre:
                return {"status": "ok", "skill": "math", "operacion": "problema_abierto",
                        "disponibles": list(ABIERTOS.keys()),
                        "nota": "Indica 'nombre' para ver el estado de uno concreto.",
                        "nivel": "abierto"}
            if nombre not in ABIERTOS:
                return {"status": "ok", "skill": "math", "operacion": "problema_abierto",
                        "nombre": nombre, "sabido": False,
                        "resultado": None,
                        "error": f"No conozco el problema '{nombre}'. Dime de que se trata "
                                 f"y lo investigamos juntos.",
                        "disponibles": list(ABIERTOS.keys()), "nivel": "abierto"}
            info = ABIERTOS[nombre]
            return {"status": "ok", "skill": "math", "operacion": "problema_abierto",
                    "nombre": nombre, "sabido": False,
                    "resultado": None,
                    "enunciado": info["enunciado"],
                    "estado": info["estado"],
                    "nota": "Este problema esta ABIERTO: no hay solucion conocida general. "
                            "No invento respuestas; si quieres, puedo ayudarte a investigarlo.",
                    "ejemplo_verificable": info.get("ejemplo_verificable"),
                    "nivel": "abierto"}

        return {
            "status": "error",
            "skill": "math",
            "error": f"Operacion '{operacion}' no reconocida.",
            "disponibles": ["suma", "resta", "multiplicacion", "division", "potencia", "raiz",
                            "factorial", "mcd", "mcm", "es_primo", "descomposicion_prima",
                            "siguiente_primo", "fibonacci", "verificar_goldbach",
                            "serie_armonica_parcial", "constante_e", "numero_pi_leibniz",
                            "problema_abierto"],
        }

    except (ValueError, TypeError, InvalidOperation) as e:
        return {"status": "error", "skill": "math", "operacion": operacion,
                "error": f"Parametros invalidos: {e}"}
    except Exception as e:
        return {"status": "error", "skill": "math", "operacion": operacion,
                "error": f"Error interno: {e}"}


def _num(v: Any) -> float:
    if v is None:
        raise ValueError("valor requerido")
    return float(v)


class ValueEntero(ValueError):
    pass


def _entero(v: Any) -> int:
    if v is None:
        raise ValueEntero("valor entero requerido")
    return int(v)
