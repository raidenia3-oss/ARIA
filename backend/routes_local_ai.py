"""
AURA Local AI & Browser Automation Routes

REST endpoints for:
- Local unrestricted AI inference (Ollama, Jan, llama.cpp)
- Browser automation (Playwright-based)
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import local AI bridge
try:
    from backend.local_ai_bridge import (
        LocalAIBridge,
        ModelConfig,
        ModelProfile,
        InferenceRequest,
        InferenceResponse,
        get_local_bridge,
        generate_unrestricted,
    )
    LOCAL_AI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Local AI bridge not available: {e}")
    LOCAL_AI_AVAILABLE = False

# Import browser automation
try:
    from backend.automation.browser_agent import (
        BrowserAgent,
        BrowserConfig,
        BrowserEngine,
        WaitStrategy,
        ActionResult,
        NavigationResult,
        RollerCoinBot,
        create_browser_agent,
    )
    BROWSER_AUTOMATION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Browser automation not available: {e}")
    BROWSER_AUTOMATION_AVAILABLE = False

# Router
local_ai_router = APIRouter(prefix="/api/local-ai", tags=["Local AI"])
browser_router = APIRouter(prefix="/api/browser", tags=["Browser Automation"])

# Global instances
_local_bridge: Optional[LocalAIBridge] = None
_browser_agent: Optional[BrowserAgent] = None
_browser_tasks: Dict[str, asyncio.Task] = {}


# ============================================================
# Local AI Models
# ============================================================

class LocalAIConfigRequest(BaseModel):
    profile: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    num_ctx: Optional[int] = None
    system_prompt: Optional[str] = None
    timeout: Optional[float] = None


class LocalAIGenerateRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stream: bool = False
    context: Optional[List[Dict[str, str]]] = None


class LocalAIGenerateResponse(BaseModel):
    message: str
    model: str
    provider: str
    tokens_generated: int
    tokens_per_second: float
    total_time: float
    prompt_tokens: int = 0
    finish_reason: str = "stop"


# ============================================================
# Browser Automation Models
# ============================================================

class BrowserInitRequest(BaseModel):
    engine: str = "chromium"
    headless: bool = True
    viewport: Optional[Dict[str, int]] = None
    user_agent: Optional[str] = None
    slow_mo: int = 0
    devtools: bool = False


class BrowserNavigateRequest(BaseModel):
    url: str
    wait_until: str = "networkidle"
    timeout: Optional[float] = None


class BrowserActionRequest(BaseModel):
    action: str
    selector: Optional[str] = None
    value: Optional[str] = None
    attribute: Optional[str] = None
    script: Optional[str] = None
    arg: Optional[Any] = None
    x: int = 0
    y: int = 0
    button: str = "left"
    click_count: int = 1
    delay: int = 0
    force: bool = False
    state: str = "visible"
    full_page: bool = True
    path: Optional[str] = None
    seconds: float = 1
    wait_until: str = "networkidle"
    timeout: Optional[float] = None


class BrowserWorkflowRequest(BaseModel):
    steps: List[Dict[str, Any]]
    stop_on_error: bool = True


class BrowserWorkflowResponse(BaseModel):
    results: List[Dict[str, Any]]
    success: bool
    completed_steps: int
    total_steps: int


# ============================================================
# Local AI Endpoints
# ============================================================

@local_ai_router.get("/health")
async def local_ai_health() -> Dict[str, Any]:
    """Check local AI bridge health and model availability."""
    if not LOCAL_AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Local AI bridge not available")
    
    global _local_bridge
    if _local_bridge is None:
        _local_bridge = get_local_bridge()
    
    health = await _local_bridge.health_check()
    return {
        "available": LOCAL_AI_AVAILABLE,
        "health": health,
        "config": _local_bridge.get_config(),
    }


@local_ai_router.get("/models")
async def local_ai_list_models() -> Dict[str, Any]:
    """List available models from the local endpoint."""
    if not LOCAL_AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Local AI bridge not available")
    
    global _local_bridge
    if _local_bridge is None:
        _local_bridge = get_local_bridge()
    
    models = await _local_bridge.list_models()
    return {"models": models, "configured_model": _local_bridge.config.model}


@local_ai_router.get("/profiles")
async def local_ai_list_profiles() -> Dict[str, Any]:
    """List available model profiles."""
    return {
        "profiles": [
            {"id": p.value, "name": p.value.replace("_", " ").title()}
            for p in ModelProfile
        ]
    }


@local_ai_router.post("/config")
async def local_ai_update_config(config: LocalAIConfigRequest) -> Dict[str, Any]:
    """Update local AI configuration."""
    if not LOCAL_AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Local AI bridge not available")
    
    global _local_bridge
    if _local_bridge is None:
        _local_bridge = get_local_bridge()
    
    update_data = config.model_dump(exclude_unset=True)
    if "profile" in update_data and update_data["profile"]:
        try:
            _local_bridge.set_profile(ModelProfile(update_data.pop("profile")))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid profile: {update_data.get('profile')}")
    
    _local_bridge.update_config(**update_data)
    return {"success": True, "config": _local_bridge.get_config()}


@local_ai_router.get("/config")
async def local_ai_get_config() -> Dict[str, Any]:
    """Get current local AI configuration."""
    if not LOCAL_AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Local AI bridge not available")
    
    global _local_bridge
    if _local_bridge is None:
        _local_bridge = get_local_bridge()
    
    return _local_bridge.get_config()


@local_ai_router.post("/generate", response_model=LocalAIGenerateResponse)
async def local_ai_generate(request: LocalAIGenerateRequest) -> LocalAIGenerateResponse:
    """Generate response from local model (non-streaming)."""
    if not LOCAL_AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Local AI bridge not available")
    
    global _local_bridge
    if _local_bridge is None:
        _local_bridge = get_local_bridge()
    
    try:
        response = await _local_bridge.generate(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=False,
            context=request.context,
        )
        return LocalAIGenerateResponse(**response.__dict__)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Generation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@local_ai_router.websocket("/generate/stream")
async def local_ai_generate_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming generation."""
    if not LOCAL_AI_AVAILABLE:
        await websocket.close(code=1011, reason="Local AI bridge not available")
        return
    
    await websocket.accept()
    global _local_bridge
    if _local_bridge is None:
        _local_bridge = get_local_bridge()
    
    try:
        while True:
            data = await websocket.receive_json()
            prompt = data.get("prompt", "")
            system_prompt = data.get("system_prompt")
            max_tokens = data.get("max_tokens")
            temperature = data.get("temperature")
            context = data.get("context")
            
            if not prompt:
                await websocket.send_json({"error": "Prompt required"})
                continue
            
            try:
                async for chunk in _local_bridge.generate_stream(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    context=context,
                ):
                    await websocket.send_json({"chunk": chunk, "done": False})
                await websocket.send_json({"chunk": "", "done": True})
            except Exception as e:
                await websocket.send_json({"error": str(e), "done": True})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e), "done": True})
        except Exception:
            pass


# ============================================================
# Browser Automation Endpoints
# ============================================================

@browser_router.get("/health")
async def browser_health() -> Dict[str, Any]:
    """Check browser automation availability."""
    return {
        "available": BROWSER_AUTOMATION_AVAILABLE,
        "initialized": _browser_agent is not None and _browser_agent._initialized,
    }


@browser_router.post("/init")
async def browser_init(config: BrowserInitRequest) -> Dict[str, Any]:
    """Initialize browser agent."""
    global _browser_agent
    
    if _browser_agent and _browser_agent._initialized:
        await _browser_agent.close()
    
    try:
        engine = BrowserEngine(config.engine)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {config.engine}")
    
    browser_config = BrowserConfig(
        engine=engine,
        headless=config.headless,
        viewport=config.viewport or {"width": 1280, "height": 720},
        user_agent=config.user_agent,
        slow_mo=config.slow_mo,
        devtools=config.devtools,
    )
    
    _browser_agent = BrowserAgent(config=browser_config)
    await _browser_agent.initialize()
    
    return {"success": True, "message": "Browser initialized"}


@browser_router.post("/close")
async def browser_close() -> Dict[str, Any]:
    """Close browser agent."""
    global _browser_agent
    if _browser_agent:
        await _browser_agent.close()
        _browser_agent = None
    return {"success": True, "message": "Browser closed"}


@browser_router.post("/navigate", response_model=Dict[str, Any])
async def browser_navigate(request: BrowserNavigateRequest) -> Dict[str, Any]:
    """Navigate to URL."""
    if not _browser_agent or not _browser_agent._initialized:
        raise HTTPException(status_code=400, detail="Browser not initialized. Call /init first.")
    
    try:
        wait_until = WaitStrategy(request.wait_until)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid wait_until: {request.wait_until}")
    
    result = await _browser_agent.navigate(request.url, wait_until, request.timeout)
    return result.__dict__


@browser_router.post("/action", response_model=Dict[str, Any])
async def browser_action(request: BrowserActionRequest) -> Dict[str, Any]:
    """Execute a browser action."""
    if not _browser_agent or not _browser_agent._initialized:
        raise HTTPException(status_code=400, detail="Browser not initialized. Call /init first.")
    
    action = request.action
    kwargs = request.model_dump(exclude={"action"}, exclude_unset=True)
    
    try:
        if action == "click":
            result = await _browser_agent.click(request.selector, **kwargs)
        elif action == "fill":
            result = await _browser_agent.fill(request.selector, request.value, **kwargs)
        elif action == "type":
            result = await _browser_agent.type_text(request.selector, request.value, **kwargs)
        elif action == "select":
            result = await _browser_agent.select_option(request.selector, **kwargs)
        elif action == "hover":
            result = await _browser_agent.hover(request.selector, **kwargs)
        elif action == "scroll":
            result = await _browser_agent.scroll(request.selector, request.x, request.y)
        elif action == "get_text":
            result = await _browser_agent.get_text(request.selector, **kwargs)
        elif action == "get_attribute":
            result = await _browser_agent.get_attribute(request.selector, request.attribute, **kwargs)
        elif action == "evaluate":
            result = await _browser_agent.evaluate(request.script, request.arg)
        elif action == "screenshot":
            result = await _browser_agent.screenshot(request.path, request.full_page, request.selector)
        elif action == "wait_for":
            wait_until = WaitStrategy(kwargs.pop("wait_until", "networkidle"))
            result = await _browser_agent.wait_for(request.selector, request.script, wait_until, request.timeout)
        elif action == "sleep":
            await asyncio.sleep(request.seconds)
            result = ActionResult(success=True, action="sleep", value=request.seconds)
        elif action == "wait_for_selector":
            result = await _browser_agent.wait_for_selector(request.selector, request.state, request.timeout)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        
        return result.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Action failed: {e}")


@browser_router.post("/workflow", response_model=BrowserWorkflowResponse)
async def browser_workflow(request: BrowserWorkflowRequest) -> BrowserWorkflowResponse:
    """Execute a multi-step workflow."""
    if not _browser_agent or not _browser_agent._initialized:
        raise HTTPException(status_code=400, detail="Browser not initialized. Call /init first.")
    
    results = await _browser_agent.execute_workflow(request.steps, request.stop_on_error)
    
    success = all(r.success for r in results)
    completed = sum(1 for r in results if r.success)
    
    return BrowserWorkflowResponse(
        results=[r.__dict__ for r in results],
        success=success,
        completed_steps=completed,
        total_steps=len(request.steps),
    )


@browser_router.get("/history")
async def browser_history(limit: int = 50) -> Dict[str, Any]:
    """Get action and navigation history."""
    if not _browser_agent:
        return {"actions": [], "navigation": []}
    
    return {
        "actions": [r.__dict__ for r in _browser_agent.get_action_history(limit)],
        "navigation": [r.__dict__ for r in _browser_agent.get_navigation_history(limit // 2)],
    }


@browser_router.post("/history/clear")
async def browser_clear_history() -> Dict[str, Any]:
    """Clear action and navigation history."""
    if _browser_agent:
        _browser_agent.clear_history()
    return {"success": True}


@browser_router.post("/screenshot")
async def browser_screenshot(path: Optional[str] = None, full_page: bool = True, selector: Optional[str] = None) -> Dict[str, Any]:
    """Take screenshot."""
    if not _browser_agent or not _browser_agent._initialized:
        raise HTTPException(status_code=400, detail="Browser not initialized")
    
    result = await _browser_agent.screenshot(path, full_page, selector)
    return result.__dict__


# RollerCoin specialized endpoints
@browser_router.post("/rollercoin/login")
async def rollercoin_login(email: str, password: str) -> Dict[str, Any]:
    """Login to RollerCoin."""
    if not _browser_agent or not _browser_agent._initialized:
        raise HTTPException(status_code=400, detail="Browser not initialized")
    
    bot = RollerCoinBot(_browser_agent)
    success = await bot.login(email, password)
    return {"success": success, "logged_in": bot.logged_in}


@browser_router.post("/rollercoin/mine")
async def rollercoin_mine(game: str = "coin_flip") -> Dict[str, Any]:
    """Start mining on RollerCoin."""
    if not _browser_agent or not _browser_agent._initialized:
        raise HTTPException(status_code=400, detail="Browser not initialized")
    
    bot = RollerCoinBot(_browser_agent)
    result = await bot.start_mining(game)
    return result.__dict__


@browser_router.post("/rollercoin/collect")
async def rollercoin_collect() -> Dict[str, Any]:
    """Collect rewards on RollerCoin."""
    if not _browser_agent or not _browser_agent._initialized:
        raise HTTPException(status_code=400, detail="Browser not initialized")
    
    bot = RollerCoinBot(_browser_agent)
    result = await bot.collect_rewards()
    return result.__dict__