import asyncio
import json
import logging
import websockets

logger = logging.getLogger("aura.mobile.ame_client")


class AMEClient:
    """AURA Mobile Engine client for testing sync connections."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self._ws = None

    @property
    def uri(self) -> str:
        return f"ws://{self.host}:{self.port}"

    async def connect(self):
        """Connect to the AME WebSocket server."""
        self._ws = await websockets.connect(self.uri)
        logger.info("Connected to AME at %s", self.uri)
        return self._ws

    async def send(self, data: dict) -> dict:
        """Send data and receive response."""
        if not self._ws:
            await self.connect()
        await self._ws.send(json.dumps(data, default=str))
        response = await self._ws.recv()
        return json.loads(response)

    async def ping(self) -> dict:
        """Test connection with a ping."""
        return await self.send({"action": "ping"})

    async def close(self):
        """Close the connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None


async def test_ame_sync():
    """
    Test AME sync connection.

    Attempts to connect to the local AME server and send a ping.
    Returns result dict with status and optional error.
    """
    client = AMEClient()
    try:
        result = await client.ping()
        logger.info("AME sync test OK: %s", result)
        return result
    except (ConnectionRefusedError, OSError) as exc:
        logger.warning("AME sync test — server offline: %s", exc)
        return {"status": "offline", "error": str(exc)}
    except Exception as exc:
        logger.error("AME sync test error: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        await client.close()
