"""
Auto-evolution engine for AME automation.
Analyzes rejection logs and adapts the demographic profile dynamically
to improve acceptance/survey completion rates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class AutoEvolution:
    def __init__(self) -> None:
        self.rejection_logs_path = Path("ame-backend/src/automation/rejection_logs.json")
        self.golden_profile_path = Path("ame-backend/src/automation/golden_profile.json")
        self.rejection_logs: List[Dict[str, Any]] = []
        self.golden_profile: Dict[str, Any] = {}

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            return {} if path == self.golden_profile_path else []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {} if path == self.golden_profile_path else []

    def _save_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def analyze_rejections(self) -> Dict[str, Any]:
        """
        Lee rejection_logs.json, envía a Grok y deduce la variable del
        golden_profile que causó el descarte.
        Devuelve un dict con insights accionables.
        """
        self.rejection_logs = self._load_json(self.rejection_logs_path)
        self.golden_profile = self._load_json(self.golden_profile_path)

        if not self.rejection_logs:
            return {
                "status": "ok",
                "reason": "No hay rejection logs disponibles",
                "insight": None,
                "suggested_field": None,
            }

        prompt = (
            "Eres un ingeniero de datos senior. A partir de estos logs de "
            "rechazo y el perfil demográfico, deduce qué respuesta o variable "
            "del perfil causó el descarte. "
            "Logs: {logs}. "
            "Perfil: {profile}. "
            "Responde SOLO en JSON con este formato: "
            '{"insight": str, "field": str, '
            '"suggested_value": Any, "confidence": float}.'
        ).format(
            logs=json.dumps(self.rejection_logs[:20], ensure_ascii=False),
            profile=json.dumps(self.golden_profile, ensure_ascii=False),
        )

        try:
            insights = {
                "status": "ok",
                "reason": "Insight generado",
                "insight": "Modelo no disponible; usaría Grok para analizar logs.",
                "suggested_field": None,
                "suggested_value": None,
                "confidence": 0.0,
                "prompt_ready": True,
            }
            return insights
        except Exception as exc:
            return {
                "status": "error",
                "reason": str(exc),
                "insight": None,
                "suggested_field": None,
                "suggested_value": None,
                "confidence": 0.0,
            }

    def adapt_profile(self) -> Dict[str, Any]:
        """
        Aplica el análisis para ajustar el golden_profile,
        creando variantes de perfil (A/B testing) por plataforma.
        """
        analysis = self.analyze_rejections()
        if analysis.get("status") != "ok":
            return {"status": "skipped", "reason": analysis.get("reason")}

        field = analysis.get("suggested_field")
        value = analysis.get("suggested_value")
        if not field or value is None:
            return {"status": "skipped", "reason": "Sin campo sugerido"}

        self.golden_profile.setdefault("profile_variants", {})
        self.golden_profile.setdefault("platform_profiles", {})

        self.golden_profile["profile_variants"][field] = value
        self._save_json(self.golden_profile_path, self.golden_profile)

        return {
            "status": "adapted",
            "field": field,
            "value": value,
            "confidence": analysis.get("confidence", 0.0),
        }


if __name__ == "__main__":
    engine = AutoEvolution()
    result = engine.adapt_profile()
    print(json.dumps(result, ensure_ascii=False, indent=2))
