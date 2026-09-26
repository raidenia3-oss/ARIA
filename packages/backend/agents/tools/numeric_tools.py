from __future__ import annotations


def _clamp(value: float = 0.0, low: float = 0.0, high: float = 1.0) -> dict:
    v = float(value)
    lo = float(low)
    hi = float(high)
    return {"value": v, "clamped": max(lo, min(hi, v)), "in_range": lo <= v <= hi}


def _average(items: list = None) -> dict:
    nums = [float(x) for x in (items or []) if x is not None]
    if not nums:
        return {"average": None, "count": 0}
    return {"average": round(sum(nums) / len(nums), 4), "count": len(nums)}


def _percent(part: float = 0.0, total: float = 0.0) -> dict:
    part = float(part)
    total = float(total)
    return {"percent": round(part / total * 100, 2) if total else None, "part": part, "total": total}


TOOLS = {
    "numeric.compute.clamp": {
        "description": "Ajusta un valor numerico a un rango [min, max].",
        "parameters": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "low": {"type": "number", "default": 0.0},
                "high": {"type": "number", "default": 1.0},
            },
            "required": ["value"],
        },
        "category": "numeric",
        "risk": "safe",
        "func": _clamp,
    },
    "numeric.compute.average": {
        "description": "Calcula el promedio de una lista de numeros.",
        "parameters": {
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"type": "number"}}},
            "required": ["items"],
        },
        "category": "numeric",
        "risk": "safe",
        "func": _average,
    },
    "numeric.compute.percent": {
        "description": "Calcula el porcentaje que representa 'part' del 'total'.",
        "parameters": {
            "type": "object",
            "properties": {
                "part": {"type": "number"},
                "total": {"type": "number"},
            },
            "required": ["part", "total"],
        },
        "category": "numeric",
        "risk": "safe",
        "func": _percent,
    },
}
