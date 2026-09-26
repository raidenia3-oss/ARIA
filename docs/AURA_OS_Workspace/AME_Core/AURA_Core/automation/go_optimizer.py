"""
GO MODE — Bucle Orientado a Objetivos
======================================
Orquestador de optimización continua de scripts/tareas.

Recibe:
  - Un script objetivo.
  - Una métrica y umbral objetivo numérico.

Ejecuta la tarea en bucle cerrado; si no cumple, usa el LLM local
para generar un parche de mejora, auto-repara el script y reintenta.
"""

from __future__ import annotations

import os
import sys
import json
import time
import tempfile
import subprocess
from pathlib import Path
from typing import Callable, Dict, Any, Optional

# Importar router local con MAX_MODE
from ..neural.local_router import LocalRouter, aplicar_max_mode


class GoOptimizer:
    """Orquestador GO_MODE."""

    def __init__(
        self,
        target_script: str | Path,
        metric_fn: Callable[[Dict[str, Any]], float],
        goal: float,
        max_iterations: int = 5,
        router: Optional[LocalRouter] = None,
    ) -> None:
        self.target_script = Path(target_script)
        self.metric_fn = metric_fn
        self.goal = goal
        self.max_iterations = max_iterations
        self.router = router or LocalRouter()
        self.history: list[Dict[str, Any]] = []

    def _read_script(self) -> str:
        return self.target_script.read_text(encoding="utf-8")

    def _write_script(self, content: str) -> None:
        self.target_script.write_text(content, encoding="utf-8")

    def _exec_script(self) -> Dict[str, Any]:
        """Ejecuta el script objetivo y retorna métricas básicas."""
        start = time.time()
        try:
            res = subprocess.run(
                [sys.executable, str(self.target_script)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            elapsed = time.time() - start
            return {
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "elapsed": elapsed,
                "success": res.returncode == 0,
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "elapsed": time.time() - start,
                "success": False,
            }

    def _build_prompt(self, execution_report: Dict[str, Any], score: float) -> str:
        rules = aplicar_max_mode("")
        return (
            "[GO_MODE]\n"
            f"Reglas del proyecto:\n{rules}\n===\n"
            "Optimiza el siguiente script Python para cumplir la métrica objetivo.\n"
            f"Métrica actual: {score:.2f}. Objetivo: {self.goal:.2f}.\n"
            "Devuelve SOLO el script completo optimizado, sin explicaciones.\n"
            f"Reporte de ejecución:\n{json.dumps(execution_report, ensure_ascii=False)[:4000]}"
        )

    async def _ask_llm_fix(self, prompt: str) -> Optional[str]:
        try:
            return await self.router.generate_code(prompt, max_mode=True)
        except Exception:
            return None

    async def run(self) -> Dict[str, Any]:
        """Bucle principal GO_MODE."""
        best_score = float("-inf")
        best_script = self._read_script()

        for i in range(1, self.max_iterations + 1):
            report = self._exec_script()
            score = self.metric_fn(report)
            iteration = {
                "iter": i,
                "score": score,
                "elapsed": report.get("elapsed", 0),
                "success": report.get("success", False),
            }
            self.history.append(iteration)

            if score >= self.goal:
                return {
                    "status": "ok",
                    "iterations": i,
                    "score": score,
                    "history": self.history,
                    "script": str(self.target_script),
                }

            prompt = self._build_prompt(report, score)
            fix = await self._ask_llm_fix(prompt)
            if not fix or not isinstance(fix, str) or "```" in fix or len(fix) < 50:
                return {
                    "status": "blocked",
                    "iterations": i,
                    "score": score,
                    "history": self.history,
                    "reason": "LLM no generó parche válido",
                }

            if score > best_score:
                best_score = score
                best_script = fix

            self._write_script(fix)

        return {
            "status": "max_iterations",
            "iterations": self.max_iterations,
            "score": best_score,
            "history": self.history,
            "script": str(self.target_script),
        }


# -------- Simulación rápida de prueba --------
def _dummy_metric(report: Dict[str, Any]) -> float:
    return 1.0 if report.get("success") else 0.0


if __name__ == "__main__":
    import asyncio

    target = Path(__file__).resolve().parents[2] / "scripts" / "health_check.py"
    optimizer = GoOptimizer(
        target_script=target, metric_fn=_dummy_metric, goal=1.0, max_iterations=3
    )
    result = asyncio.run(optimizer.run())
    print(json.dumps(result, ensure_ascii=False, indent=2))
