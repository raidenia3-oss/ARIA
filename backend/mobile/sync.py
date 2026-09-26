import asyncio
import json
import logging
import platform
import subprocess
from typing import Dict, Any, Set
from dataclasses import dataclass, field

logger = logging.getLogger("aura.mobile.sync")


@dataclass
class SyncEvent:
    """Represents a sync event between mobile and desktop."""
    action: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=asyncio.get_event_loop)


class SyncManager:
    """Manages WebSocket connections and data sync between mobile and desktop."""

    def __init__(self):
        self._connections: Set[Any] = set()
        self._pending_sync: list = []

    async def add_connection(self, websocket):
        """Register a new WebSocket connection."""
        self._connections.add(websocket)
        logger.info("Mobile connection added (total: %d)", len(self._connections))

    async def remove_connection(self, websocket):
        """Remove a WebSocket connection."""
        self._connections.discard(websocket)
        logger.info("Mobile connection removed (total: %d)", len(self._connections))

    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast data to all connected mobile clients."""
        message = json.dumps(data, default=str)
        dead = set()
        for ws in self._connections:
            try:
                await ws.send(message)
            except Exception as exc:
                logger.warning("Broadcast failed to %s: %s", ws, exc)
                dead.add(ws)
        for ws in dead:
            await self.remove_connection(ws)

    async def send_to(self, websocket, data: Dict[str, Any]):
        """Send data to a specific client."""
        try:
            await websocket.send(json.dumps(data, default=str))
        except Exception as exc:
            logger.warning("Send to client failed: %s", exc)
            await self.remove_connection(websocket)

    async def sync_data(self, websocket, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming sync data from a mobile client."""
        action = data.get("action", "unknown")
        payload = data.get("data", {})

        logger.info("Sync action '%s' from %s", action, getattr(websocket, "remote_address", ""))

        result = {"status": "ok", "action": action}

        if action == "ping":
            result["data"] = {"pong": True}
        elif action == "get_conversations":
            result["data"] = {"conversations": []}
        elif action == "get_settings":
            result["data"] = {"theme": "dark", "language": "es"}
        elif action == "push_message":
            await self.broadcast({"type": "message", "data": payload})
            result["data"] = {"echo": True}
        elif action == "get_system_info":
            result["data"] = {
                "hostname": platform.node(),
                "platform": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "cpu_count": platform.processor() or "unknown",
            }
        elif action == "execute_termux":
            cmd = payload.get("command", "")
            whitelist = {
                "ls", "cat", "pwd", "whoami", "df", "ps", "uptime",
                "date", "hostname", "uname",
            }
            cmd_token = cmd.split()[0] if cmd.split() else ""
            if cmd_token not in whitelist:
                result = {"status": "denied", "reason": f"Command '{cmd_token}' not in whitelist"}
            else:
                try:
                    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    result["data"] = {
                        "command": cmd,
                        "returncode": proc.returncode,
                        "stdout": proc.stdout.strip(),
                        "stderr": proc.stderr.strip(),
                    }
                except subprocess.TimeoutExpired:
                    result = {"status": "timeout", "action": action}
                except Exception as exc:
                    result = {"status": "error", "error": str(exc)}
        elif action == "toggle_mode":
            current = payload.get("mode", "remote")
            result["data"] = {"mode": current, "switched": True}
        elif action == "get_mode":
            result["data"] = {"mode": "remote"}
        else:
            result = {"status": "unknown_action", "action": action}

        return result


sync_manager = SyncManager()


async def mobile_sync(websocket):
    """WebSocket handler for mobile-desktop sync."""
    await sync_manager.add_connection(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                response = await sync_manager.sync_data(websocket, data)
                await sync_manager.send_to(websocket, response)
            except json.JSONDecodeError:
                await sync_manager.send_to(websocket, {"status": "error", "detail": "Invalid JSON"})
    except Exception as exc:
        logger.error("Mobile sync error: %s", exc)
    finally:
        await sync_manager.remove_connection(websocket)
