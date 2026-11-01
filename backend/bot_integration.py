# -*- coding: utf-8 -*-
"""
Integración BotManager + GrookBot + ExplorerBot con cerebro unificado (ARIA).
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from backend.bot_manager import bot_manager
from backend.grook_bot import GrookBot
from backend.brain_orchestrator import brain

try:
    from backend.explorer.explorer_bot import ExplorerBot
    from backend.explorer.explorer_api import explorer_manager
except Exception:
    ExplorerBot = None  # type: ignore
    explorer_manager = None  # type: ignore


class BotIntegration:
    def __init__(self) -> None:
        self.bot_manager = bot_manager
        self.instances: Dict[str, Any] = {}
        self._sync()

    def _sync(self) -> None:
        for bid, b in bot_manager.bots.items():
            if bid in self.instances:
                continue
            if b.type == 'grook':
                try:
                    self.instances[bid] = GrookBot(name=b.name, brain=brain)
                    if b.status == 'running':
                        self.instances[bid].start()
                except Exception:
                    pass
            elif b.type == 'explorer' and ExplorerBot is not None:
                try:
                    inst = ExplorerBot(name=b.name)
                    self.instances[bid] = inst
                    if explorer_manager is not None:
                        try:
                            explorer_manager.instances[bid] = inst
                        except Exception:
                            pass
                    if b.status == 'running':
                        inst.start()
                except Exception:
                    pass

    def create_grook(self, name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = bot_manager.create_bot(name, bot_type='grook', config=config or {})
        bid = res.get('bot_id')
        if bid:
            try:
                self.instances[bid] = GrookBot(name=name, brain=brain)
            except Exception:
                pass
        return res

    def create_explorer(self, name: str = 'explorer', config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            if explorer_manager is not None:
                res = explorer_manager.create_explorer(name=name)
                bid = res.get('bot_id')
                if bid:
                    try:
                        if bid in explorer_manager.instances:
                            self.instances[bid] = explorer_manager.instances[bid]
                    except Exception:
                        pass
                return res
        except Exception:
            pass
        res = bot_manager.create_bot(name, bot_type='explorer', config=config or {})
        bid = res.get('bot_id')
        if bid and ExplorerBot is not None:
            try:
                inst = ExplorerBot(name=name)
                self.instances[bid] = inst
                if explorer_manager is not None:
                    try:
                        explorer_manager.instances[bid] = inst
                    except Exception:
                        pass
            except Exception:
                pass
        return res

    def start(self, bot_id: str) -> Dict[str, Any]:
        res = bot_manager.start_bot(bot_id)
        if res.get('status') == 'started' and bot_id in self.instances:
            try:
                self.instances[bot_id].start()
            except Exception:
                pass
        return res

    def stop(self, bot_id: str) -> Dict[str, Any]:
        res = bot_manager.stop_bot(bot_id)
        if res.get('status') == 'stopped' and bot_id in self.instances:
            try:
                self.instances[bot_id].stop()
            except Exception:
                pass
        return res

    def tick_all(self) -> Dict[str, Any]:
        out = {}
        for bid, inst in self.instances.items():
            try:
                out[bid] = inst.tick()
            except Exception as e:
                out[bid] = {'status': 'error', 'error': str(e)}
        return out

    def chat(self, bot_id: str, msg: str) -> Dict[str, Any]:
        inst = self.instances.get(bot_id)
        if not inst:
            return {'status': 'not_found'}
        try:
            return inst.chat(msg)
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


bot_integration = BotIntegration()
