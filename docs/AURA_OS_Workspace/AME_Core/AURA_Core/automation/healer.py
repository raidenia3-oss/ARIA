"""
Auto-Evolución y Tolerancia a Fallos (Self-Healing) para automatizaciones basadas en Playwright.

- Captura excepciones de timeout/selector inexistente.
- Extrae DOM y screenshot.
- Consulta al LLM central (Hugging Face Space) para obtener un selector corregido.
- Aplica el nuevo selector en caliente y notifica al HUD de JARVIS por WebSocket.
"""

from __future__ import annotations

import json
import re
import os
import time
import traceback
from pathlib import Path
from typing import Optional

ALERT_WS_URL = "ws://localhost:8765"

SELECTORS_FILE = Path(__file__).with_name("selectors.json")


def _safe_selector_key(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]+", "_", name).strip("_").lower()


def load_selector_map() -> dict:
    if SELECTORS_FILE.exists():
        try:
            return json.loads(SELECTORS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_selector_map(mapping: dict) -> None:
    SELECTORS_FILE.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")


def update_selector(alias: str, new_selector: str) -> str:
    mapping = load_selector_map()
    mapping[alias] = new_selector
    save_selector_map(mapping)
    return new_selector


def get_selector(alias: str, fallback: Optional[str] = None) -> Optional[str]:
    mapping = load_selector_map()
    value = mapping.get(alias, fallback)
    return value


class AutoHealingError(Exception):
    """Error de automatización potencialmente recuperable."""


class Healer:
    def __init__(self, llm_client=None, ws_client=None, screenshot_dir: Optional[Path] = None):
        self.llm = llm_client
        self.ws = ws_client
        self.screenshot_dir = screenshot_dir or Path(__file__).parent / "heal_screenshots"
        self.screenshot_dir.mkdir(exist_ok=True)

    def _emit(self, event_type: str, payload: dict):
        if not self.ws:
            return
        try:
            msg = {"node": "AURA_HEALER", "event": event_type, "payload": payload}
            text = json.dumps(msg, ensure_ascii=False)
            if hasattr(self.ws, "send_text"):
                self.ws.send_text(text)
            elif hasattr(self.ws, "send"):
                import asyncio

                asyncio.run(self.ws.send(text))
        except Exception:
            pass

    def _screenshot(self, page, step: str) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = self.screenshot_dir / f"{step}_{ts}.png"
        try:
            path.write_bytes(page.screenshot())
        except Exception:
            pass
        return path

    def _dom_fragment(self, page, max_chars: int = 4000) -> str:
        try:
            html = page.content()
        except Exception:
            return ""
        if len(html) > max_chars:
            return html[:max_chars] + "...[truncado]"
        return html

    def heal(
        self, page, alias: str, current_selector: str, error: Exception, step: str = "rollercoin"
    ):
        key = _safe_selector_key(alias)
        shot = self._screenshot(page, step)
        dom = self._dom_fragment(page)
        error_text = "".join(traceback.format_exception_only(type(error), error)).strip()
        candidate = self._ask_llm_for_selector(dom, error_text, current_selector)
        if not candidate:
            raise AutoHealingError(f"No se pudo regenerar selector para alias={alias}")
        candidate = candidate.strip()
        if not (
            candidate.startswith("css=")
            or candidate.startswith("xpath=")
            or candidate.startswith("/")
            or candidate.startswith(".")
        ):
            candidate = f"css={candidate}"
        new_selector = update_selector(key, candidate)
        self._emit(
            "automation_healing_success",
            {
                "alias": alias,
                "old_selector": current_selector,
                "new_selector": new_selector,
                "screenshot": str(shot),
                "step": step,
            },
        )
        # FASE 28 - Retroalimentación cognitiva: registrar reparación en KnowledgeGraph
        self._registrar_reparacion_en_grafo(alias, current_selector, new_selector, step)
        return new_selector

    def _ask_llm_for_selector(
        self, html_fragment: str, error_text: str, current_selector: str
    ) -> Optional[str]:
        if self.llm is None:
            return None
        system_prompt = (
            "Analiza este HTML antiguo y el error de automatización. "
            "Devuelve única y exclusivamente la nueva cadena del selector CSS o XPath corregido "
            'en formato JSON sin texto adicional, ejemplo: {"selector": "css=.nuevo"}.'
        )
        user_prompt = json.dumps(
            {
                "html": html_fragment,
                "error": error_text,
                "selector_actual": current_selector,
            },
            ensure_ascii=False,
        )
        try:
            answer = self.llm.chat(
                system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0
            )
            if not isinstance(answer, str):
                return None
            m = re.search(r"\{.*\}", answer, re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(0))
            return data.get("selector")
        except Exception:
            return None

    def _registrar_reparacion_en_grafo(
        self, alias: str, old_selector: str, new_selector: str, step: str
    ) -> None:
        """Registra la reparación en KnowledgeGraph para construir histórico semántico."""
        try:
            from AURA_Core.memory.knowledge_graph import KnowledgeGraph
            from AURA_Core.event_manager import EventManager

            kg = KnowledgeGraph()
            kg.add_node(
                "Bot_Rollercoin",
                tipo="actor",
                atributos={"modulo": "automation", "step": step},
            )
            safe_alias = alias.replace(" ", "_").replace("/", "_")
            selector_node_id = f"Selector_{safe_alias}"
            kg.add_node(
                selector_node_id,
                tipo="selector",
                atributos={
                    "nuevo": new_selector,
                    "viejo": old_selector,
                    "step": step,
                },
            )
            kg.add_relation(
                "Bot_Rollercoin",
                selector_node_id,
                "REPARADO_CON",
                atributos={"timestamp": time.time(), "step": step},
            )
            kg._save()
            em = EventManager()
            if hasattr(em, "broadcast"):
                em.broadcast(
                    {
                        "tipo": "healer_knowledge_update",
                        "origen": "Bot_Rollercoin",
                        "destino": selector_node_id,
                        "relacion": "REPARADO_CON",
                        "step": step,
                        "timestamp": time.time(),
                    }
                )
        except Exception as exc:
            pass
