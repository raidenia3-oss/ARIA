"""
AURA Web Automation Agent — Autonomous browser automation for local web interaction.

Supports Playwright for reliable, headless browser automation.
Capable of interacting with DOM elements, handling dynamic content,
and executing complex workflows on sites like RollerCoin, faucets, and web apps.

Features:
- Headless/headful browser modes
- Element interaction (click, type, select, hover, scroll)
- Wait strategies (network idle, selector, function, timeout)
- Screenshot and PDF capture
- Cookie/storage management
- Script injection and evaluation
- Session persistence
- Error recovery and retry logic
"""

from __future__ import annotations

import os
import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        BrowserContext,
        Page,
        Playwright,
        ElementHandle,
        Locator,
        Response,
        Request,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Install with: pip install playwright && playwright install")


class WaitStrategy(str, Enum):
    """Strategies for waiting for page/element states."""
    NETWORK_IDLE = "networkidle"
    DOM_CONTENT_LOADED = "domcontentloaded"
    LOAD = "load"
    SELECTOR = "selector"
    FUNCTION = "function"
    TIMEOUT = "timeout"


class BrowserEngine(str, Enum):
    """Supported browser engines."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


@dataclass
class BrowserConfig:
    """Configuration for browser automation."""
    engine: BrowserEngine = BrowserEngine.CHROMIUM
    headless: bool = True
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1280, "height": 720})
    user_agent: Optional[str] = None
    locale: str = "es-ES"
    timezone_id: str = "Europe/Madrid"
    permissions: List[str] = field(default_factory=list)
    proxy: Optional[Dict[str, str]] = None
    downloads_path: Optional[str] = None
    accept_downloads: bool = True
    ignore_https_errors: bool = True
    java_script_enabled: bool = True
    bypass_csp: bool = True
    slow_mo: int = 0
    devtools: bool = False
    args: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.args:
            self.args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]


@dataclass
class ActionResult:
    """Result of a browser action."""
    success: bool
    action: str
    selector: Optional[str] = None
    value: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NavigationResult:
    """Result of a navigation action."""
    success: bool
    url: str
    status: Optional[int] = None
    error: Optional[str] = None
    duration_ms: float = 0
    timestamp: float = field(default_factory=time.time)
    redirects: List[str] = field(default_factory=list)


class BrowserAgent:
    """
    Autonomous web automation agent for local browser interaction.
    
    Uses Playwright for reliable cross-browser automation.
    Designed for tasks like:
    - RollerCoin / faucet automation
    - Form filling and submission
    - Data extraction from dynamic pages
    - Multi-step workflows
    - Screenshot capture for verification
    """
    
    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        session_dir: str = "data/browser_sessions",
        default_timeout: float = 30.0,
    ) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not available. Install: pip install playwright && playwright install")
        
        self.config = config or BrowserConfig()
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.default_timeout = default_timeout * 1000  # Convert to ms
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._initialized = False
        self._action_history: List[ActionResult] = []
        self._navigation_history: List[NavigationResult] = []
        self._event_listeners: Dict[str, List[Callable]] = {}
        
        # Default args for stability
        if not self.config.args:
            self.config.args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
    
    async def initialize(self) -> None:
        """Initialize browser, context, and page."""
        if self._initialized:
            return
        
        self._playwright = await async_playwright().start()
        
        launch_options = {
            "headless": self.config.headless,
            "slow_mo": self.config.slow_mo,
            "devtools": self.config.devtools,
            "args": self.config.args,
        }
        
        if self.config.proxy:
            launch_options["proxy"] = self.config.proxy
        
        engine = getattr(self._playwright, self.config.engine.value)
        self._browser = await engine.launch(**launch_options)
        
        context_options = {
            "viewport": self.config.viewport,
            "locale": self.config.locale,
            "timezone_id": self.config.timezone_id,
            "ignore_https_errors": self.config.ignore_https_errors,
            "java_script_enabled": self.config.java_script_enabled,
            "bypass_csp": self.config.bypass_csp,
            "accept_downloads": self.config.accept_downloads,
        }
        
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent
        if self.config.permissions:
            context_options["permissions"] = self.config.permissions
        if self.config.downloads_path:
            context_options["downloads_path"] = self.config.downloads_path
        
        self._context = await self._browser.new_context(**context_options)
        
        # Add stealth scripts
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es', 'en'] });
        """)
        
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.default_timeout)
        
        # Set up request/response logging
        self._page.on("request", self._on_request)
        self._page.on("response", self._on_response)
        self._page.on("pageerror", self._on_page_error)
        self._page.on("console", self._on_console)
        
        self._initialized = True
        logger.info(f"BrowserAgent initialized: {self.config.engine.value} ({'headless' if self.config.headless else 'headful'})")
    
    async def close(self) -> None:
        """Close browser and cleanup."""
        if self._page:
            await self._page.close()
            self._page = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._initialized = False
        logger.info("BrowserAgent closed")
    
    async def __aenter__(self) -> "BrowserAgent":
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    def _record_action(self, result: ActionResult) -> None:
        self._action_history.append(result)
        if len(self._action_history) > 1000:
            self._action_history = self._action_history[-500:]
    
    def _record_navigation(self, result: NavigationResult) -> None:
        self._navigation_history.append(result)
        if len(self._navigation_history) > 100:
            self._navigation_history = self._navigation_history[-50:]
    
    def _on_request(self, request: Request) -> None:
        self._emit("request", {"url": request.url, "method": request.method, "resource_type": request.resource_type})
    
    def _on_response(self, response: Response) -> None:
        self._emit("response", {"url": response.url, "status": response.status, "headers": dict(response.headers)})
    
    def _on_page_error(self, error: Exception) -> None:
        self._emit("page_error", {"error": str(error)})
        logger.warning(f"Page error: {error}")
    
    def _on_console(self, msg) -> None:
        self._emit("console", {"type": msg.type, "text": msg.text, "location": msg.location})
    
    def _emit(self, event: str, data: Any) -> None:
        for callback in self._event_listeners.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Event listener error: {e}")
    
    def on(self, event: str, callback: Callable) -> None:
        """Register event listener."""
        if event not in self._event_listeners:
            self._event_listeners[event] = []
        self._event_listeners[event].append(callback)
    
    def off(self, event: str, callback: Callable) -> None:
        """Remove event listener."""
        if event in self._event_listeners:
            self._event_listeners[event] = [c for c in self._event_listeners[event] if c != callback]
    
    @property
    def page(self) -> Page:
        """Get current page."""
        if not self._page:
            raise RuntimeError("Browser not initialized. Call initialize() first.")
        return self._page
    
    @property
    def context(self) -> BrowserContext:
        """Get browser context."""
        if not self._context:
            raise RuntimeError("Browser not initialized. Call initialize() first.")
        return self._context
    
    async def navigate(
        self,
        url: str,
        wait_until: WaitStrategy = WaitStrategy.NETWORK_IDLE,
        timeout: Optional[float] = None,
    ) -> NavigationResult:
        """Navigate to URL with configurable wait strategy."""
        start = time.time()
        try:
            if not self._initialized:
                await self.initialize()
            
            response = await self._page.goto(
                url,
                wait_until=wait_until.value,
                timeout=timeout * 1000 if timeout else self.default_timeout,
            )
            
            duration = (time.time() - start) * 1000
            result = NavigationResult(
                success=True,
                url=self._page.url,
                status=response.status if response else None,
                duration_ms=duration,
                redirects=[r.url for r in response.redirect_chain] if response else [],
            )
            self._record_navigation(result)
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = NavigationResult(
                success=False,
                url=url,
                error=str(e),
                duration_ms=duration,
            )
            self._record_navigation(result)
            return result
    
    async def wait_for(
        self,
        selector: Optional[str] = None,
        function: Optional[str] = None,
        wait_until: WaitStrategy = WaitStrategy.NETWORK_IDLE,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Wait for various conditions."""
        start = time.time()
        try:
            if selector:
                await self._page.wait_for_selector(selector, timeout=timeout * 1000 if timeout else self.default_timeout)
                return ActionResult(success=True, action="wait_for_selector", selector=selector, duration_ms=(time.time()-start)*1000)
            elif function:
                await self._page.wait_for_function(function, timeout=timeout * 1000 if timeout else self.default_timeout)
                return ActionResult(success=True, action="wait_for_function", value=function, duration_ms=(time.time()-start)*1000)
            else:
                await self._page.wait_for_load_state(wait_until.value, timeout=timeout * 1000 if timeout else self.default_timeout)
                return ActionResult(success=True, action="wait_for_load", value=wait_until.value, duration_ms=(time.time()-start)*1000)
        except Exception as e:
            return ActionResult(success=False, action="wait", error=str(e), duration_ms=(time.time()-start)*1000)
    
    async def click(
        self,
        selector: str,
        button: str = "left",
        click_count: int = 1,
        delay: int = 0,
        force: bool = False,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Click an element."""
        start = time.time()
        try:
            await self._page.click(
                selector,
                button=button,
                click_count=click_count,
                delay=delay,
                force=force,
                timeout=timeout * 1000 if timeout else self.default_timeout,
            )
            result = ActionResult(success=True, action="click", selector=selector, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="click", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def fill(
        self,
        selector: str,
        value: str,
        delay: int = 0,
        force: bool = False,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Fill an input field."""
        start = time.time()
        try:
            await self._page.fill(
                selector,
                value,
                delay=delay,
                force=force,
                timeout=timeout * 1000 if timeout else self.default_timeout,
            )
            result = ActionResult(success=True, action="fill", selector=selector, value=value, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="fill", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def type_text(
        self,
        selector: str,
        text: str,
        delay: int = 50,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Type text character by character."""
        start = time.time()
        try:
            await self._page.type(
                selector,
                text,
                delay=delay,
                timeout=timeout * 1000 if timeout else self.default_timeout,
            )
            result = ActionResult(success=True, action="type", selector=selector, value=text, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="type", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def select_option(
        self,
        selector: str,
        value: Optional[str] = None,
        label: Optional[str] = None,
        index: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Select option in a dropdown."""
        start = time.time()
        try:
            if value is not None:
                await self._page.select_option(selector, value=value, timeout=timeout * 1000 if timeout else self.default_timeout)
            elif label is not None:
                await self._page.select_option(selector, label=label, timeout=timeout * 1000 if timeout else self.default_timeout)
            elif index is not None:
                await self._page.select_option(selector, index=index, timeout=timeout * 1000 if timeout else self.default_timeout)
            else:
                raise ValueError("Must provide value, label, or index")
            
            result = ActionResult(success=True, action="select", selector=selector, value=value or label or index, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="select", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def hover(
        self,
        selector: str,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Hover over an element."""
        start = time.time()
        try:
            await self._page.hover(selector, timeout=timeout * 1000 if timeout else self.default_timeout)
            result = ActionResult(success=True, action="hover", selector=selector, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="hover", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def scroll(
        self,
        selector: Optional[str] = None,
        x: int = 0,
        y: int = 0,
    ) -> ActionResult:
        """Scroll page or element."""
        start = time.time()
        try:
            if selector:
                await self._page.locator(selector).scroll(off_x=x, off_y=y)
            else:
                await self._page.evaluate(f"window.scrollBy({x}, {y})")
            result = ActionResult(success=True, action="scroll", selector=selector, value={"x": x, "y": y}, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="scroll", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def get_text(
        self,
        selector: str,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Get text content of an element."""
        start = time.time()
        try:
            text = await self._page.locator(selector).inner_text(timeout=timeout * 1000 if timeout else self.default_timeout)
            result = ActionResult(success=True, action="get_text", selector=selector, value=text, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="get_text", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def get_attribute(
        self,
        selector: str,
        attribute: str,
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Get attribute value of an element."""
        start = time.time()
        try:
            value = await self._page.locator(selector).get_attribute(attribute, timeout=timeout * 1000 if timeout else self.default_timeout)
            result = ActionResult(success=True, action="get_attribute", selector=selector, value={attribute: value}, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="get_attribute", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def evaluate(
        self,
        script: str,
        arg: Any = None,
    ) -> ActionResult:
        """Evaluate JavaScript in page context."""
        start = time.time()
        try:
            result_value = await self._page.evaluate(script, arg)
            result = ActionResult(success=True, action="evaluate", value=result_value, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="evaluate", error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def evaluate_handle(
        self,
        script: str,
        arg: Any = None,
    ) -> ActionResult:
        """Evaluate JavaScript and return element handle."""
        start = time.time()
        try:
            handle = await self._page.evaluate_handle(script, arg)
            result = ActionResult(success=True, action="evaluate_handle", value="ElementHandle", duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="evaluate_handle", error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def screenshot(
        self,
        path: Optional[str] = None,
        full_page: bool = True,
        selector: Optional[str] = None,
    ) -> ActionResult:
        """Take screenshot of page or element."""
        start = time.time()
        try:
            if not path:
                path = str(self.session_dir / f"screenshot_{int(time.time()*1000)}.png")
            
            if selector:
                await self._page.locator(selector).screenshot(path=path)
            else:
                await self._page.screenshot(path=path, full_page=full_page)
            
            result = ActionResult(success=True, action="screenshot", selector=selector, value=path, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="screenshot", error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def pdf(
        self,
        path: str,
        format: str = "A4",
        print_background: bool = True,
    ) -> ActionResult:
        """Generate PDF of current page."""
        start = time.time()
        try:
            await self._page.pdf(path=path, format=format, print_background=print_background)
            result = ActionResult(success=True, action="pdf", value=path, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="pdf", error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def get_cookies(self, urls: Optional[List[str]] = None) -> ActionResult:
        """Get cookies."""
        start = time.time()
        try:
            cookies = await self._context.cookies(urls)
            result = ActionResult(success=True, action="get_cookies", value=cookies, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="get_cookies", error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> ActionResult:
        """Set cookies."""
        start = time.time()
        try:
            await self._context.add_cookies(cookies)
            result = ActionResult(success=True, action="set_cookies", value={"count": len(cookies)}, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="set_cookies", error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def clear_cookies(self) -> ActionResult:
        """Clear all cookies."""
        start = time.time()
        try:
            await self._context.clear_cookies()
            result = ActionResult(success=True, action="clear_cookies", duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="clear_cookies", error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: Optional[float] = None,
    ) -> ActionResult:
        """Wait for element to reach state."""
        start = time.time()
        try:
            await self._page.wait_for_selector(selector, state=state, timeout=timeout * 1000 if timeout else self.default_timeout)
            result = ActionResult(success=True, action="wait_for_selector", selector=selector, value=state, duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
        except Exception as e:
            result = ActionResult(success=False, action="wait_for_selector", selector=selector, error=str(e), duration_ms=(time.time()-start)*1000)
            self._record_action(result)
            return result
    
    async def execute_workflow(
        self,
        steps: List[Dict[str, Any]],
        stop_on_error: bool = True,
    ) -> List[ActionResult]:
        """
        Execute a multi-step workflow.
        
        Steps format:
        [
            {"action": "navigate", "url": "https://example.com"},
            {"action": "click", "selector": "#login"},
            {"action": "fill", "selector": "#username", "value": "user"},
            {"action": "fill", "selector": "#password", "value": "pass"},
            {"action": "click", "selector": "#submit"},
            {"action": "wait_for", "selector": ".dashboard"},
            {"action": "screenshot", "path": "login_success.png"},
        ]
        """
        results = []
        for i, step in enumerate(steps):
            action = step.get("action")
            try:
                if action == "navigate":
                    result = await self.navigate(step["url"], wait_until=WaitStrategy(step.get("wait_until", "networkidle")))
                elif action == "click":
                    result = await self.click(step["selector"], **{k: v for k, v in step.items() if k not in ["action", "selector"]})
                elif action == "fill":
                    result = await self.fill(step["selector"], step["value"], **{k: v for k, v in step.items() if k not in ["action", "selector", "value"]})
                elif action == "type":
                    result = await self.type_text(step["selector"], step["value"], **{k: v for k, v in step.items() if k not in ["action", "selector", "value"]})
                elif action == "select":
                    result = await self.select_option(step["selector"], **{k: v for k, v in step.items() if k not in ["action", "selector"]})
                elif action == "hover":
                    result = await self.hover(step["selector"])
                elif action == "scroll":
                    result = await self.scroll(step.get("selector"), step.get("x", 0), step.get("y", 0))
                elif action == "get_text":
                    result = await self.get_text(step["selector"])
                elif action == "get_attribute":
                    result = await self.get_attribute(step["selector"], step["attribute"])
                elif action == "evaluate":
                    result = await self.evaluate(step["script"], step.get("arg"))
                elif action == "screenshot":
                    result = await self.screenshot(step.get("path"), step.get("full_page", True), step.get("selector"))
                elif action == "wait_for":
                    result = await self.wait_for(step.get("selector"), step.get("function"), WaitStrategy(step.get("wait_until", "networkidle")))
                elif action == "sleep":
                    await asyncio.sleep(step.get("seconds", 1))
                    result = ActionResult(success=True, action="sleep", value=step.get("seconds", 1), duration_ms=step.get("seconds", 1)*1000)
                else:
                    result = ActionResult(success=False, action=action or "unknown", error=f"Unknown action: {action}")
                
                results.append(result)
                
                if not result.success and stop_on_error:
                    logger.error(f"Workflow stopped at step {i}: {result.error}")
                    break
                    
            except Exception as e:
                result = ActionResult(success=False, action=action or "unknown", error=str(e))
                results.append(result)
                if stop_on_error:
                    break
        
        return results
    
    def get_action_history(self, limit: int = 50) -> List[ActionResult]:
        """Get recent action history."""
        return self._action_history[-limit:]
    
    def get_navigation_history(self, limit: int = 20) -> List[NavigationResult]:
        """Get recent navigation history."""
        return self._navigation_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear action and navigation history."""
        self._action_history.clear()
        self._navigation_history.clear()


class RollerCoinBot:
    """
    Specialized automation for RollerCoin.
    Handles login, mining, missions, and token collection.
    """
    
    def __init__(self, agent: BrowserAgent) -> None:
        self.agent = agent
        self.base_url = "https://rollercoin.com"
        self.logged_in = False
    
    async def login(self, email: str, password: str) -> bool:
        """Login to RollerCoin."""
        await self.agent.navigate(f"{self.base_url}/login")
        await self.agent.fill('input[name="email"]', email)
        await self.agent.fill('input[name="password"]', password)
        result = await self.agent.click('button[type="submit"]')
        await self.agent.wait_for(selector=".user-menu, .profile, [data-testid=user-menu]", timeout=15)
        self.logged_in = result.success
        return self.logged_in
    
    async def start_mining(self, game: str = "coin_flip") -> ActionResult:
        """Start a mining game."""
        if not self.logged_in:
            return ActionResult(success=False, action="start_mining", error="Not logged in")
        
        await self.agent.navigate(f"{self.base_url}/game/{game}")
        await self.agent.wait_for(selector="canvas, .game-container", timeout=20)
        return await self.agent.click('button:has-text("Start"), button:has-text("Jugar")')
    
    async def collect_rewards(self) -> ActionResult:
        """Collect available rewards."""
        if not self.logged_in:
            return ActionResult(success=False, action="collect_rewards", error="Not logged in")
        
        await self.agent.navigate(f"{self.base_url}/rewards")
        return await self.agent.click('button:has-text("Claim"), button:has-text("Reclamar")')


async def create_browser_agent(
    headless: bool = True,
    engine: BrowserEngine = BrowserEngine.CHROMIUM,
    session_dir: str = "data/browser_sessions",
) -> BrowserAgent:
    """Factory function to create and initialize a browser agent."""
    config = BrowserConfig(
        engine=engine,
        headless=headless,
    )
    agent = BrowserAgent(config=config, session_dir=session_dir)
    await agent.initialize()
    return agent