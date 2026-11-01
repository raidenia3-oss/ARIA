# ARIA Core Expanded - orquesta todo
from __future__ import annotations
from typing import Any, Dict

from .visual_core import core_visual, nucleo, expressor, gitlens
from .universal_connector import universal_connector
from .web_learner import web_learner
from .bot_integration import bot_integration
from .brain_orchestrator import brain


class AriaExpanded:
    def __init__(self) -> None:
        pass

    def awaken(self, passphrase: str = "aria") -> Dict[str, Any]:
        return {
            "visual": core_visual.activate_full(passphrase),
            "status": "awakened",
            "nucleo_state": nucleo.status(),
            "expressor": expressor.status(),
        }

    def learn_project(self, path_or_url: str, is_url: bool = False) -> Dict[str, Any]:
        if is_url and path_or_url.startswith('http'):
            return web_learner.learn_url(path_or_url)
        return gitlens.learn_repo(path_or_url)

    def bot_list(self) -> Dict[str, Any]:
        return bot_integration.bot_manager.list_bots()

    def think(self, prompt: str) -> Dict[str, Any]:
        return brain.think(prompt)


aria_expanded = AriaExpanded()
