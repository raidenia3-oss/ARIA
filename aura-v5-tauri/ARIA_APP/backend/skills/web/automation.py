import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    if action == "playwright_navigate":
        return _playwright_navigate(params)
    elif action == "playwright_click":
        return _playwright_click(params)
    elif action == "playwright_screenshot":
        return _playwright_screenshot(params)
    elif action == "playwright_get_text":
        return _playwright_get_text(params)
    elif action == "playwright_fill":
        return _playwright_fill(params)
    return {"error": f"Unknown action: {action}"}


def _get_driver():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright().start()
    except Exception as e:
        return None


def _playwright_navigate(params: Dict[str, Any]) -> Dict[str, Any]:
    p = _get_driver()
    if not p:
        return {"error": "Playwright not available. Install with: pip install playwright && playwright install chromium"}
    try:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        url = params.get("url", "")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = page.title()
        text = page.inner_text("body")[:3000]
        browser.close()
        p.stop()
        return {"status": "ok", "url": url, "title": title, "text": text}
    except Exception as e:
        try:
            browser.close()
            p.stop()
        except Exception:
            pass
        return {"error": str(e)}


def _playwright_click(params: Dict[str, Any]) -> Dict[str, Any]:
    p = _get_driver()
    if not p:
        return {"error": "Playwright not available"}
    try:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(params.get("url", ""), wait_until="domcontentloaded", timeout=30000)
        selector = params.get("selector", "")
        page.click(selector, timeout=10000)
        title = page.title()
        browser.close()
        p.stop()
        return {"status": "ok", "title": title}
    except Exception as e:
        try:
            browser.close()
            p.stop()
        except Exception:
            pass
        return {"error": str(e)}


def _playwright_screenshot(params: Dict[str, Any]) -> Dict[str, Any]:
    p = _get_driver()
    if not p:
        return {"error": "Playwright not available"}
    try:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(params.get("url", ""), wait_until="domcontentloaded", timeout=30000)
        path = params.get("path", f"browser_{int(time.time())}.png")
        page.screenshot(path=path, full_page=True)
        browser.close()
        p.stop()
        return {"status": "ok", "path": path}
    except Exception as e:
        try:
            browser.close()
            p.stop()
        except Exception:
            pass
        return {"error": str(e)}


def _playwright_get_text(params: Dict[str, Any]) -> Dict[str, Any]:
    p = _get_driver()
    if not p:
        return {"error": "Playwright not available"}
    try:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(params.get("url", ""), wait_until="domcontentloaded", timeout=30000)
        selector = params.get("selector", "body")
        text = page.inner_text(selector)[:5000]
        browser.close()
        p.stop()
        return {"status": "ok", "text": text}
    except Exception as e:
        try:
            browser.close()
            p.stop()
        except Exception:
            pass
        return {"error": str(e)}


def _playwright_fill(params: Dict[str, Any]) -> Dict[str, Any]:
    p = _get_driver()
    if not p:
        return {"error": "Playwright not available"}
    try:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(params.get("url", ""), wait_until="domcontentloaded", timeout=30000)
        page.fill(params.get("selector", ""), params.get("value", ""))
        browser.close()
        p.stop()
        return {"status": "ok"}
    except Exception as e:
        try:
            browser.close()
            p.stop()
        except Exception:
            pass
        return {"error": str(e)}
