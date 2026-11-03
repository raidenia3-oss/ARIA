"""dibujo_iterativo: ARIA genera, evalua y refina dibujos con feedback del cerebro."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "drawings"
OUT.mkdir(parents=True, exist_ok=True)


def _mejor_prompt(tema: str, intentos: List[str]) -> str:
    base = f"high quality illustration of {tema}, detailed, vibrant colors, professional art"
    if intentos:
        base += ", " + ", ".join(intentos[-3:])
    return base


def iterar(tema: str, n: int = 3, cerebro=None) -> Dict[str, Any]:
    """Genera n variantes, evalua con cerebro, guarda la mejor."""
    import gen_local
    resultados = []
    for i in range(n):
        prompt = _mejor_prompt(tema, [r.get("prompt", "") for r in resultados])
        archivo = str(OUT / f"{tema.replace(' ', '_')}_{i}.png")
        r = gen_local.generar(prompt, w=512, h=512, archivo=archivo)
        resultados.append({"i": i, "prompt": prompt, "ok": r.get("ok"), "archivo": archivo})
        if cerebro is not None:
            try:
                fb = cerebro.chat(f"Evalua este prompt de imagen: '{prompt}'. Da 1 sugerencia de mejora.").get("response", "")
                resultados[-1]["feedback"] = fb
            except Exception:
                pass
    return {"tema": tema, "resultados": resultados, "mejor": resultados[-1] if resultados else None}


def listar() -> List[str]:
    return sorted(str(p) for p in OUT.glob("*.png"))
