# -*- coding: utf-8 -*-
"""ARIA OS - LongMemory MCP Integration.

Integra el servidor MCP LongMemory para memoria persistente y búsqueda semántica.
Basado en: https://github.com/CaviarOSS/LongMemory

Endpoints:
  POST /api/memory/mcp/query           - Query LongMemory via MCP
  POST /api/memory/mcp/store           - Store memory via MCP
  GET  /api/memory/mcp/servers         - List MCP servers
  POST /api/memory/mcp/servers         - Add MCP server
  GET  /api/memory/mcp/health          - Health check
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("ARIA.LongMemoryMCP")

router = APIRouter(prefix="/api/memory/mcp", tags=["longmemory-mcp"])

# ============================================================================
# Models
# ============================================================================

class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"  # stdio, sse, http


class MCPQueryRequest(BaseModel):
    server: str = "longmemory"
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    namespace: str = "default"


class MCPQueryResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int
    latency_ms: int


class MCPStoreRequest(BaseModel):
    server: str = "longmemory"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    namespace: str = "default"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MCPStoreResponse(BaseModel):
    id: str
    status: str
    latency_ms: int


class MCPServerInfo(BaseModel):
    name: str
    status: str
    tools: List[str] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)


# ============================================================================
# MCP Client
# ============================================================================

_mcp_servers: Dict[str, Dict] = {}
_mcp_processes: Dict[str, subprocess.Popen] = {}


def _get_longmemory_path() -> Optional[Path]:
    """Find LongMemory MCP server path."""
    # Check common locations
    candidates = [
        Path.home() / ".aria" / "mcp" / "longmemory" / "server.py",
        Path.home() / "LongMemory" / "server.py",
        Path("C:/LongMemory/server.py"),
        Path("/opt/longmemory/server.py"),
    ]
    
    for c in candidates:
        if c.exists():
            return c
    
    # Check if installed via pip
    try:
        import longmemory_mcp
        return Path(longmemory_mcp.__file__).parent / "server.py"
    except ImportError:
        pass
    
    return None


async def _call_mcp_tool(server_name: str, tool: str, args: Dict) -> Dict:
    """Call an MCP tool via stdio transport."""
    server = _mcp_servers.get(server_name)
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP server {server_name} not configured")
    
    proc = _mcp_processes.get(server_name)
    
    # Start process if not running
    if proc is None or proc.poll() is not None:
        proc = await _start_mcp_server(server_name, server)
        if proc is None:
            raise HTTPException(status_code=503, detail=f"Failed to start MCP server {server_name}")
    
    # Send request
    request = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "name": tool,
            "arguments": args
        }
    }
    
    try:
        proc.stdin.write((json.dumps(request) + "\n").encode())
        await proc.stdin.drain()
        
        # Read response
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=30.0)
        response = json.loads(line.decode())
        
        if "error" in response:
            raise HTTPException(status_code=500, detail=response["error"].get("message", "MCP error"))
        
        return response.get("result", {})
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="MCP server timeout")
    except Exception as e:
        logger.error(f"MCP call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _start_mcp_server(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Start MCP server process."""
    try:
        proc = await asyncio.create_subprocess_exec(
            config["command"],
            *config["args"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **config.get("env", {})}
        )
        
        _mcp_processes[name] = proc
        
        # Wait for initialization
        await asyncio.sleep(1)
        
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "aria-os", "version": "5.0.0"}
            }
        }
        
        proc.stdin.write((json.dumps(init_request) + "\n").encode())
        await proc.stdin.drain()
        
        # Read initialize response
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
        logger.info(f"MCP server {name} initialized")
        
        return proc
    except Exception as e:
        logger.error(f"Failed to start MCP server {name}: {e}")
        return None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/query", response_model=MCPQueryResponse)
async def mcp_query(req: MCPQueryRequest):
    """Query LongMemory via MCP."""
    start = time.time()
    
    try:
        result = await _call_mcp_tool(
            req.server,
            "search_memory",
            {
                "query": req.query,
                "top_k": req.top_k,
                "namespace": req.namespace
            }
        )
        
        # Parse results
        memories = []
        if isinstance(result, dict):
            if "memories" in result:
                memories = result["memories"]
            elif "results" in result:
                memories = result["results"]
            elif "content" in result:
                memories = [result]
        
        return MCPQueryResponse(
            results=memories,
            total=len(memories),
            latency_ms=int((time.time() - start) * 1000)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store", response_model=MCPStoreResponse)
async def mcp_store(req: MCPStoreRequest):
    """Store memory via MCP."""
    start = time.time()
    
    try:
        result = await _call_mcp_tool(
            req.server,
            "store_memory",
            {
                "content": req.content,
                "metadata": req.metadata,
                "namespace": req.namespace,
                "importance": req.importance
            }
        )
        
        memory_id = result.get("id", result.get("memory_id", str(int(time.time() * 1000))))
        
        return MCPStoreResponse(
            id=memory_id,
            status="stored",
            latency_ms=int((time.time() - start) * 1000)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP store failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers", response_model=List[MCPServerInfo])
async def list_mcp_servers():
    """List configured MCP servers."""
    return [
        MCPServerInfo(
            name=name,
            status="running" if _mcp_processes.get(name) and _mcp_processes[name].poll() is None else "stopped",
            tools=info.get("tools", []),
            resources=info.get("resources", [])
        )
        for name, info in _mcp_servers.items()
    ]


@router.post("/servers", response_model=Dict[str, Any])
async def add_mcp_server(config: MCPServerConfig):
    """Add MCP server configuration."""
    if config.name in _mcp_servers:
        raise HTTPException(status_code=400, detail=f"Server {config.name} already exists")
    
    # Validate command exists
    if config.transport == "stdio":
        try:
            # Test if command is available
            proc = await asyncio.create_subprocess_exec(
                config.command, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
        except:
            logger.warning(f"Command {config.command} may not be available")
    
    _mcp_servers[config.name] = config.model_dump()
    
    # Auto-discover tools
    try:
        proc = await _start_mcp_server(config.name, config.model_dump())
        if proc:
            # List tools
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            proc.stdin.write((json.dumps(tools_request) + "\n").encode())
            await proc.stdin.drain()
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
            tools_result = json.loads(line.decode())
            _mcp_servers[config.name]["tools"] = [t["name"] for t in tools_result.get("result", {}).get("tools", [])]
    except Exception as e:
        logger.warning(f"Could not discover tools for {config.name}: {e}")
    
    return {"status": "added", "server": config.name}


@router.delete("/servers/{name}", response_model=Dict[str, Any])
async def remove_mcp_server(name: str):
    """Remove MCP server configuration."""
    if name not in _mcp_servers:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")
    
    # Stop process if running
    proc = _mcp_processes.get(name)
    if proc and proc.poll() is None:
        proc.terminate()
        await proc.wait()
    
    del _mcp_servers[name]
    if name in _mcp_processes:
        del _mcp_processes[name]
    
    return {"status": "removed", "server": name}


@router.post("/servers/{name}/start", response_model=Dict[str, Any])
async def start_mcp_server(name: str):
    """Start MCP server."""
    if name not in _mcp_servers:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")
    
    proc = await _start_mcp_server(name, _mcp_servers[name])
    if proc:
        return {"status": "started", "server": name}
    else:
        raise HTTPException(status_code=500, detail="Failed to start server")


@router.post("/servers/{name}/stop", response_model=Dict[str, Any])
async def stop_mcp_server(name: str):
    """Stop MCP server."""
    proc = _mcp_processes.get(name)
    if proc and proc.poll() is None:
        proc.terminate()
        await proc.wait()
        return {"status": "stopped", "server": name}
    
    return {"status": "not_running", "server": name}


@router.get("/health")
async def mcp_health():
    """Health check for MCP integration."""
    await _auto_configure_longmemory()
    
    longmemory_path = _get_longmemory_path()
    
    servers = []
    for name, info in _mcp_servers.items():
        proc = _mcp_processes.get(name)
        servers.append({
            "name": name,
            "status": "running" if proc and proc.poll() is None else "stopped",
            "command": info.get("command"),
            "tools": info.get("tools", [])
        })
    
    return {
        "longmemory_available": longmemory_path is not None,
        "longmemory_path": str(longmemory_path) if longmemory_path else None,
        "configured_servers": len(_mcp_servers),
        "running_servers": sum(1 for p in _mcp_processes.values() if p.poll() is None),
        "servers": servers,
        "timestamp": time.time()
    }


# ============================================================================
# Auto-configure LongMemory if available
# ============================================================================

async def _auto_configure_longmemory():
    """Auto-configure LongMemory MCP server if available."""
    path = _get_longmemory_path()
    if path:
        config = MCPServerConfig(
            name="longmemory",
            command="python",
            args=[str(path)],
            env={}
        )
        _mcp_servers["longmemory"] = config.model_dump()
        logger.info(f"Auto-configured LongMemory MCP server at {path}")


def init_longmemory_mcp():
    """Initialize LongMemory MCP - call during app startup."""
    pass  # Auto-configuration happens on first request