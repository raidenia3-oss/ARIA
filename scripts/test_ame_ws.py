import asyncio
import json
import sys
import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8000/api/mobile/sync/test-cli"
    try:
        async with websockets.connect(uri, open_timeout=10, close_timeout=10) as ws:
            print("WS connected")
            await ws.send(json.dumps({"type": "auth", "token": "test-token"}))
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(raw)
            print("auth response:", data)
            if data.get("auth") != "accepted":
                print("AUTH_REJECTED")
                sys.exit(2)

            await ws.send(json.dumps({"type": "ping"}))
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(raw)
            print("ping response:", data)
    except Exception as exc:
        print("WS_ERROR:", exc)
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())
