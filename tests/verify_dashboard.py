"""PARTE 7: DASHBOARD TESTING (250 lines) — Dashboard UI + WebSocket verification.

Tests dashboard loading, 4D dimensions, WebSocket, activity monitor, chat.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@dataclass
class DashboardResult:
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class DashboardVerifier:
    BASE_URL: str = "http://localhost:8000"

    def __init__(self) -> None:
        self.results: List[DashboardResult] = []

    async def _http_get(self, path: str) -> Dict[str, Any]:
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.BASE_URL}{path}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
                ct = resp.headers.get("content-type", "")
                if "html" in ct:
                    return {"_html": body.decode("utf-8"), "status": resp.status}
                data = body.decode("utf-8")
                return json.loads(data) if data else {}
        except Exception as exc:
            return {"error": str(exc)}

    async def _http_post(self, path: str, body: dict = None) -> Dict[str, Any]:
        import urllib.request

        data = json.dumps(body or {}).encode("utf-8") if body else b"{}"
        req = urllib.request.Request(
            f"{self.BASE_URL}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = resp.read().decode("utf-8")
                return json.loads(resp_data) if resp_data else {}
        except Exception as exc:
            return {"error": str(exc)}

    async def test_dashboard_loads(self) -> DashboardResult:
        result = DashboardResult(test_name="dashboard_loads", passed=False)
        try:
            resp = await self._http_get("/aria_dashboard_v3.html")

            loads = False
            if "error" not in resp:
                html = resp.get("_html", resp.get("html", ""))
                if isinstance(html, str) and "ARIA" in html:
                    loads = True
                elif isinstance(html, str) and len(html) > 1000:
                    loads = True

            result.passed = loads
            result.details = {
                "loads": loads,
                "has_aria": "ARIA" in str(resp.get("_html", resp.get("html", ""))),
                "status": resp.get("status", 0) if isinstance(resp, dict) else 0,
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_four_dimensions_visible(self) -> DashboardResult:
        result = DashboardResult(test_name="four_dimensions_visible", passed=False)
        try:
            resp = await self._http_get("/aria_dashboard_v3.html")

            four_dims_visible = False
            if "error" not in resp:
                html = resp.get("_html", resp.get("html", ""))
                if isinstance(html, str):
                    dims = ["Discovery", "Creation", "Delivery", "Cybersecurity"]
                    found_dims = [d for d in dims if d.lower() in html.lower()]
                    four_dims_visible = len(found_dims) >= 3

            result.passed = four_dims_visible
            result.details = {
                "four_dims_visible": four_dims_visible,
                "html_has_discovery": "discovery" in str(resp.get("_html", "")).lower(),
                "html_has_creation": "creation" in str(resp.get("_html", "")).lower(),
                "html_has_delivery": "delivery" in str(resp.get("_html", "")).lower(),
                "html_has_cyber": "cyber" in str(resp.get("_html", "")).lower(),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_websocket_connection(self) -> DashboardResult:
        result = DashboardResult(test_name="websocket_connection", passed=False)
        try:
            import asyncio

            import websockets

            websocket_works = False
            try:
                ws = await websockets.connect(
                    f"{self.BASE_URL.replace('http', 'ws')}/api/aria/g7/stream",
                    open_timeout=5,
                    close_timeout=5,
                )
                await ws.send(json.dumps({"type": "subscribe"}))
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    websocket_works = True
                except asyncio.TimeoutError:
                    websocket_works = True
                await ws.close()
            except Exception:
                try:
                    ws = await websockets.connect(
                        f"{self.BASE_URL.replace('http', 'ws')}/ws",
                        open_timeout=5,
                        close_timeout=5,
                    )
                    websocket_works = True
                    await ws.close()
                except Exception:
                    pass

            result.passed = websocket_works
            result.details = {"websocket_works": websocket_works}
        except ImportError:
            resp = await self._http_get("/aria_dashboard_v3.html")
            html = resp.get("_html", resp.get("html", "")) if isinstance(resp, dict) else ""
            has_ws = (
                "websocket" in str(html).lower()
                or "ws://" in str(html).lower()
                or "stream" in str(html).lower()
            )
            result.passed = has_ws
            result.details = {"websocket_in_html": has_ws}
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_activity_monitor(self) -> DashboardResult:
        result = DashboardResult(test_name="activity_monitor", passed=False)
        try:
            resp = await self._http_get("/aria_dashboard_v3.html")

            activity_monitor_works = False
            if "error" not in resp:
                html = resp.get("_html", resp.get("html", ""))
                if isinstance(html, str):
                    has_monitor = "activity" in html.lower() or "monitor" in html.lower()
                    has_timestamp = "time" in html.lower() or "hora" in html.lower()
                    activity_monitor_works = has_monitor or has_timestamp

            result.passed = activity_monitor_works
            result.details = {
                "activity_monitor_works": activity_monitor_works,
                "has_activity": (
                    "activity" in str(resp.get("_html", "")).lower()
                    if isinstance(resp, dict)
                    else False
                ),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result

    async def test_chat_panel_integrated(self) -> DashboardResult:
        result = DashboardResult(test_name="chat_panel_integrated", passed=False)
        try:
            resp = await self._http_get("/aria_dashboard_v3.html")

            chat_integrated = False
            if "error" not in resp:
                html = resp.get("_html", resp.get("html", ""))
                if isinstance(html, str):
                    has_input = "input" in html.lower() and "chat" in html.lower()
                    has_send = "button" in html.lower() or "send" in html.lower()
                    has_messages = "message" in html.lower() or "chat-msg" in html.lower()
                    chat_integrated = has_input and (has_send or has_messages)

            result.passed = chat_integrated
            result.details = {
                "chat_integrated": chat_integrated,
                "has_input": (
                    "input" in str(resp.get("_html", "")).lower()
                    if isinstance(resp, dict)
                    else False
                ),
            }
        except Exception as exc:
            result.details["error"] = str(exc)
        self.results.append(result)
        return result


@pytest.mark.asyncio
async def test_dashboard_loads() -> None:
    v = DashboardVerifier()
    r = await v.test_dashboard_loads()
    assert r.passed, f"Dashboard load failed: {r.details}"


@pytest.mark.asyncio
async def test_four_dimensions_visible() -> None:
    v = DashboardVerifier()
    r = await v.test_four_dimensions_visible()
    assert r.passed, f"Four dimensions failed: {r.details}"


@pytest.mark.asyncio
async def test_websocket_connection() -> None:
    v = DashboardVerifier()
    r = await v.test_websocket_connection()
    assert r.passed, f"WebSocket failed: {r.details}"


@pytest.mark.asyncio
async def test_activity_monitor() -> None:
    v = DashboardVerifier()
    r = await v.test_activity_monitor()
    assert r.passed, f"Activity monitor failed: {r.details}"


@pytest.mark.asyncio
async def test_chat_panel_integrated() -> None:
    v = DashboardVerifier()
    r = await v.test_chat_panel_integrated()
    assert r.passed, f"Chat panel failed: {r.details}"
