"""Dependency-free stdio MCP client bridging ARIA to Rea (morluto/rea).

REA is an MCP server launched through ``npx rea-agents mcp`` (see rea.tools).
This module speaks MCP over stdio with *no* third-party Python dependencies
(JSON-RPC 2.0 + ``Content-Length`` framing, like LSP), so the AURA venv is not
enlarged. A single shared session is kept warm and reused across tool calls.

Lifetime:
    client = ReaMcpClient()
    await client.ensure()              # spawn + initialize + tools/list
    tools = await client.list_tools()  # cached after the first call
    result = await client.call_tool("binary_session", {})
    await client.close()

The command/version are configurable so operators can pin a release:
    REA_MCP_COMMAND="npx -y rea-agents@6.4.0 mcp"
    REA_MCP_NODE, REA_MCP_VERSION, REA_MCP_ARGS
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.ReaMCP")

_PROTOCOL_VERSION = "2025-11-25"
_CLIENT_INFO = {"name": "ARIA", "version": "2.1.0"}

READINESS_PING_INTERVAL = 5.0


def _default_command() -> Tuple[str, List[str]]:
    """Return (executable, args) to launch the REA stdio MCP server.

    On Windows ``npx`` is a ``.cmd`` shim that ``CreateProcess`` cannot exec
    directly, so REA's own docs wrap it in ``cmd.exe /d /c`` — we do the same.
    Operators may override the whole vector via ``REA_MCP_COMMAND`` (space split)
    or ``REA_MCP_ARGS``.
    """
    raw = os.environ.get("REA_MCP_COMMAND")
    if raw:
        parts = raw.split()
        return parts[0], parts[1:]
    if os.environ.get("REA_MCP_ARGS"):
        parts = os.environ["REA_MCP_ARGS"].split()
        return parts[0], parts[1:]
    version = os.environ.get("REA_MCP_VERSION", "latest")
    if os.name == "nt":
        return "cmd", ["/d", "/c", "npx", "-y", f"rea-agents@{version}", "mcp"]
    return "npx", ["-y", f"rea-agents@{version}", "mcp"]


class McpError(Exception):
    """Raised on an MCP protocol error or transport failure."""


class ReaMcpClient:
    """One stdio MCP connection to the REA server, lazily initialized."""

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        startup_timeout: float = 90.0,
        tool_timeout: float = 120.0,
    ) -> None:
        cmd, default_args = _default_command()
        self._command = command or cmd
        self._args = args or default_args
        self._env = env
        self._startup_timeout = startup_timeout
        self._tool_timeout = tool_timeout
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.Task] = None
        self._send_lock = asyncio.Lock()
        self._id_lock = asyncio.Lock()
        self._pending: Dict[int, asyncio.Future] = {}
        self._next_id = 1
        self._tools: List[Dict[str, Any]] = []
        self._connected = False
        self._tools_loaded = False
        self._ready_at: Optional[float] = None

    async def ensure(self) -> None:
        if self._connected:
            return
        async with self._id_lock:
            if self._connected:
                return
            await asyncio.wait_for(self._connect(), timeout=self._startup_timeout)
            await self._handshake()
            self._connected = True
            self._ready_at = time.time()
            logger.info("REA MCP session ready in %.1fs", time.time() - (self._ready_at or time.time()))
            await self.list_tools()

    async def _connect(self) -> None:
        env = dict(os.environ)
        if self._env:
            env.update(self._env)
        env.setdefault("NODE_NO_WARNINGS", "1")
        # REA may emit progress/log on stderr; keep it out of the JSON-RPC channel.
        create_new = os.name == "nt"
        kwargs: Dict[str, Any] = {
            "stdin": asyncio.subprocess.PIPE,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "env": env,
        }
        if create_new:
            kwargs["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP (win)
        self._proc = await asyncio.create_subprocess_exec(
            self._command, *self._args, **kwargs
        )
        if sys.platform == "win32" and self._proc.stderr:
            asyncio.create_task(self._drain_stderr(self._proc.stderr))
        self._reader = asyncio.create_task(self._read_loop())

    async def _drain_stderr(self, stream: asyncio.StreamReader) -> None:
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                logger.debug("rea-stderr: %s", line.decode("utf-8", "replace").rstrip())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("rea-stderr drain ended: %s", exc)

    async def _read_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            while True:
                msg = await self._read_message(self._proc.stdout)
                if msg is None:
                    break
                self._dispatch(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("rea-stderr read loop ended: %s", exc)
        finally:
            self._fail_pending(McpError("rea transport closed"))
            self._connected = False
            self._tools_loaded = False

    @staticmethod
    async def _read_exact(reader: asyncio.StreamReader, n: int) -> bytes:
        try:
            return await reader.readexactly(n)
        except asyncio.IncompleteReadError as exc:
            raise EOFError(str(exc))

    async def _read_message(self, stream: asyncio.StreamReader) -> Optional[Dict[str, Any]]:
        header = await self._read_headers(stream)
        if header is None:
            return None
        length = int(header.get("content-length", 0))
        if length <= 0:
            return None
        body = await self._read_exact(stream, length)
        return json.loads(body.decode("utf-8"))

    @staticmethod
    async def _read_headers(stream: asyncio.StreamReader) -> Optional[Dict[str, str]]:
        buf = bytearray()
        sep = b"\r\n\r\n"
        alt = b"\n\n"
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                if not buf:
                    return None
                break
            buf.extend(chunk)
            idx = buf.find(sep)
            if idx == -1:
                idx = buf.find(alt)
            if idx != -1:
                break
        raw = bytes(buf[: idx + len(sep)] if buf.find(sep) != -1 else buf[: idx + len(alt)])
        text = raw.decode("latin-1")
        headers: Dict[str, str] = {}
        for line in text.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
        return headers

    def _dispatch(self, msg: Dict[str, Any]) -> None:
        if "id" not in msg:
            return  # notification
        rid = msg.get("id")
        future = self._pending.pop(rid, None)
        if future is None:
            return
        if "error" in msg:
            future.set_exception(McpError(json.dumps(msg["error"], ensure_ascii=False)))
        else:
            future.set_result(msg.get("result"))

    def _fail_pending(self, err: Exception) -> None:
        for fut in list(self._pending.values()):
            if not fut.done():
                try:
                    fut.set_exception(err)
                except Exception:
                    pass
        self._pending.clear()

    async def _send_notification(self, msg: Dict[str, Any]) -> None:
        await self._send_base({"jsonrpc": "2.0", **msg}, with_id=False)

    async def _send_base(self, msg: Dict[str, Any], with_id: bool = True) -> Any:
        await self.ensure()
        async with self._id_lock:
            req_id = self._next_id
            self._next_id += 1
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        frame = json.dumps({**msg, "id": req_id}).encode("utf-8")
        async with self._send_lock:
            assert self._proc is not None and self._proc.stdin is not None
            self._proc.stdin.write(
                f"Content-Length: {len(frame)}\r\n\r\n".encode("latin-1") + frame
            )
            await self._proc.stdin.drain()
        if not with_id:
            self._pending.pop(req_id, None)
            return None
        return await asyncio.wait_for(future, timeout=self._tool_timeout)

    async def _send_request(self, method: str, params: Any = None) -> Any:
        return await self._send_base({"method": method, "params": params or {}}, with_id=True)

    async def _handshake(self) -> None:
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"prompts": {}, "resources": {}, "tools": {}},
                "clientInfo": _CLIENT_INFO,
            },
        )
        if not isinstance(result, dict):
            raise McpError(f"unexpected initialize result: {result!r}")
        await self._send_notification({"method": "notifications/initialized", "params": {}})
        logger.debug("rea initialize: %s", result.get("serverInfo", {}))

    async def list_tools(self) -> List[Dict[str, Any]]:
        if self._tools_loaded:
            return self._tools
        result = await self._send_request("tools/list")
        tools = result.get("tools", []) if isinstance(result, dict) else []
        if not isinstance(tools, list):
            tools = []
        self._tools = tools
        self._tools_loaded = True
        return self._tools

    def cached_tools(self) -> List[Dict[str, Any]]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a REA tool and return a normalized result.

        Returns ``{"content", "is_error", "meta", "structured"}``. ``content``
        joins the text blocks; ``structured`` is the canonical
        ``structuredContent.normalized_result`` when the tool emits Evidence.
        """
        await self.ensure()
        result = await self._send_request(
            "tools/call", {"name": name, "arguments": arguments or {}},
        )
        content = result.get("content") or []
        texts: List[str] = []
        structured = None
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                texts.append(block.get("text", ""))
            elif btype == "structured":
                structured = block.get("structured")
            if btype == "text" and not structured:
                # REA also surfaces structuredContent under the text block meta
                meta = block.get("_meta") or {}
                val = meta.get("structuredContent") or meta.get("structured_content")
                if isinstance(val, dict):
                    structured = val
        if not structured and isinstance(result, dict):
            structured = result.get("structuredContent") or result.get("structured_content")
        return {
            "content": "\n".join(texts),
            "text_blocks": content,
            "is_error": bool(result.get("isError")),
            "meta": result.get("_meta"),
            "structured": structured,
            "normalized": (structured or {}).get("normalized_result") if structured else None,
            "evidence_id": (structured or {}).get("evidence_id"),
        }

    async def close(self) -> None:
        if self._reader is not None and not self._reader.done():
            self._reader.cancel()
            try:
                await self._reader
            except Exception:
                pass
        self._reader = None
        proc = self._proc
        if proc is not None:
            try:
                proc.stdin.close() if proc.stdin else None
            except Exception:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except Exception:
                self._kill_tree(proc)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except Exception:
                    pass
        self._proc = None
        self._connected = False
        self._tools_loaded = False

    @staticmethod
    def _kill_tree(proc: asyncio.subprocess.Process) -> None:
        """Kill the whole process tree (cmd -> npx -> node on Windows).

        Solo se toca el arbol que ARIA lanzo. El ProcessGuard decide: si el
        PID no es hijo de ARIA, no se toca.
        """
        try:
            if os.name == "nt":
                import subprocess as _sp
                try:
                    from backend.process_guard import get_guard
                    verdict = get_guard().check(proc.pid)
                except Exception:
                    try:
                        from ARIA_APP.backend.process_guard import get_guard
                        verdict = get_guard().check(proc.pid)
                    except Exception:
                        verdict = None
                if verdict is not None and not verdict.allowed:
                    logger.info("kill_tree omitido: %s", verdict.reason)
                    return
                _sp.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                )
            else:
                os.killpg(os.getpgid(proc.pid), 9)
        except Exception as exc:
            logger.debug("kill_tree failed: %s", exc)


_client: Optional[ReaMcpClient] = None


def get_rea_client() -> ReaMcpClient:
    global _client
    if _client is None:
        version = os.environ.get("REA_MCP_VERSION", "latest")
        _client = ReaMcpClient(startup_timeout=float(os.environ.get("REA_MCP_STARTUP_TIMEOUT", "90")))
        # record version for the HUD/status endpoint
        _client._version = version  # type: ignore[assignment]
    return _client


def reset_rea_client() -> None:
    global _client
    if _client is not None:
        asyncio.get_event_loop().create_task(_client.close())
        _client = None
