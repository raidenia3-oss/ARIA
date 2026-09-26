"""
Platform adapters for AME automation.
Handle login flows for target survey platforms.
"""

from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path
from typing import Any, Dict, Optional

from automation.stealth_engine import Infiltrator


class PlatformAdapters:
    def __init__(self, infiltrator: Optional[Infiltrator] = None) -> None:
        self.infiltrator = infiltrator or Infiltrator()
        self.targets_path = Path("ame-backend/src/config/targets.json")
        self.targets = self._load_targets()
        self.bot_email = os.getenv("BOT_EMAIL", "")
        self.bot_password = os.getenv("BOT_PASSWORD", "")

    def _load_targets(self) -> list:
        if not self.targets_path.exists():
            return []
        try:
            import json

            return json.loads(self.targets_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    async def close_popups(self) -> None:
        candidates = [
            "button[aria-label='Close']",
            "button[aria-label='Cerrar']",
            ".close",
            "[data-testid='close']",
            "button:has-text('Close')",
            "button:has-text('Cerrar')",
            "button:has-text('×')",
            "text=×",
        ]
        for sel in candidates:
            try:
                el = await self.infiltrator.page.wait_for_selector(sel, timeout=1200)
                if el:
                    await el.click()
                    await asyncio.sleep(random.uniform(0.3, 0.7))
            except Exception:
                continue

    async def login_to_platform(self, platform_name: str) -> Dict[str, Any]:
        target = next((p for p in self.targets if p.get("platform") == platform_name), None)
        if not target:
            return {"status": "error", "reason": f"Unknown platform: {platform_name}"}
        login_url = target.get("login_url") or target.get("base_url")
        selectors = target.get("selectors", {})
        email_sel = selectors.get("email", "input[type='email']")
        password_sel = selectors.get("password", "input[type='password']")
        submit_sel = selectors.get("submit", "button[type='submit']")
        await self.infiltrator.start()
        try:
            await self.infiltrator.smart_navigate(login_url)
            await self.close_popups()
            try:
                await self.infiltrator.smart_type(email_sel, self.bot_email)
            except Exception:
                pass
            try:
                await self.infiltrator.smart_type(password_sel, self.bot_password)
            except Exception:
                pass
            try:
                await self.infiltrator.smart_click(submit_sel)
            except Exception:
                pass
            await asyncio.sleep(random.uniform(2.0, 4.0))
            await self.close_popups()
            return {"status": "ok", "platform": platform_name, "url": self.infiltrator.page.url}
        except Exception as exc:
            return {"status": "error", "platform": platform_name, "reason": str(exc)}
        finally:
            await self.infiltrator.stop()
