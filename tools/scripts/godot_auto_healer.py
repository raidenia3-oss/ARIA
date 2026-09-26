#!/usr/bin/env python3
"""
AURA Godot Auto-Healer v3
Corrección universal de GDScript para Godot 4.6.
Aplica fixes seguros a TODOS los archivos .gd del proyecto.

Uso:
    python scripts/godot_auto_healer.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GODOT_SCRIPTS_DIR = PROJECT_ROOT / "godot"
AURA_BACKEND_URL = os.getenv("AURA_BACKEND_URL", "http://localhost:8000")
AURA_API_KEY = os.getenv("AURA_API_KEY", "")
MEMORY_REMEMBER_ENDPOINT = "/memory/remember"
CHAT_ENDPOINT = "/api/chat"


class GodotAutoHealer:
    def __init__(self, backend_url: str = AURA_BACKEND_URL, api_key: str = AURA_API_KEY) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key
        self.headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.backend_url}{endpoint}",
            data=data,
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as exc:
            print(f"[AutoHealer] Error en {endpoint}: {exc}")
            return None

    def apply_fixes_to_file(self, path: Path) -> bool:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return False

        original = text

        text = re.sub(r'Control\.LayoutPreset\.', 'Control.PRESET_', text)
        text = re.sub(r'(?<!strip_)\.strip\(\)(?!\s*\))', '.strip_edges()', text)
        text = re.sub(r'add_theme_font_size\(', 'add_theme_font_size_override(', text)
        text = re.sub(r'set_border_width_all\((\d+)\)', lambda m: 'set_border_width_left(' + m.group(1) + ')\n\t\tset_border_width_right(' + m.group(1) + ')\n\t\tset_border_width_top(' + m.group(1) + ')\n\t\tset_border_width_bottom(' + m.group(1) + ')', text)
        text = re.sub(r'Color\.from_string\(([^,]+),\s*Color\.WHITE\)', r'Color(\1)', text)
        text = re.sub(r'Color\.from_string\(([^,]+),\s*Color\.BLACK\)', r'Color(\1)', text)
        text = re.sub(r'Color\.from_string\(([^,]+),\s*Color\.RED\)', r'Color(\1)', text)
        text = re.sub(r'Color\.from_string\(([^,]+),\s*Color\.GREEN\)', r'Color(\1)', text)
        text = text.replace('maxf(', 'max(')
        text = text.replace('String | null', 'Variant')
        text = re.sub(r'await\s+audio_player\.finished', 'audio_player.finished', text)

        patterns = [
            (r'await\s+get_tree\(\)\.process_frame', 'pass # get_tree().process_frame'),
            (r'await\s+_probe_backend\([^)]+\)', '_probe_backend(url)'),
            (r'await\s+_post_json\([^)]+\)', '_post_json(endpoint, payload)'),
            (r'await\s+_get_json\([^)]+\)', '_get_json(endpoint)'),
            (r'await\s+_request_json\([^)]+\)', '_request_json(path)'),
            (r'await\s+AuraClient\.(request_json|scan_wifi|query_api)\([^)]*\)', 'AuraClient.\1(endpoint)'),
            (r'await\s+dashboard\.query_api\([^)]+\)', 'dashboard.query_api(endpoint)'),
            (r'await\s+_client\.(request_json|_probe_backend)\([^)]*\)', '_client.\1(...)'),
        ]

        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)

        if text != original:
            try:
                path.write_text(text, encoding="utf-8")
                return True
            except Exception:
                pass
        return False

    def run(self) -> bool:
        print("[AutoHealer] Iniciando corrección universal de Godot...")
        if not GODOT_SCRIPTS_DIR.exists():
            print(f"[AutoHealer] Directorio no encontrado: {GODOT_SCRIPTS_DIR}")
            return False

        gd_files = list(GODOT_SCRIPTS_DIR.rglob("*.gd"))
        print(f"[AutoHealer] Archivos .gd encontrados: {len(gd_files)}")

        applied = 0
        for path in gd_files:
            if self.apply_fixes_to_file(path):
                print(f"[AutoHealer] Corregido: {path.relative_to(PROJECT_ROOT)}")
                applied += 1

        print(f"[AutoHealer] Fixes aplicados: {applied}/{len(gd_files)}")
        return applied > 0


def main() -> int:
    healer = GodotAutoHealer()
    success = healer.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
