import asyncio, json, websockets
from search.aura_search import AURASearchEngine, SearchQuery
from search.geo_search import GeoSearch

class SearchNode:

    def __init__(self, ws_url="ws://localhost:8765"):
        self.ws_url = ws_url
        self.engine = AURASearchEngine()
        self.geo    = GeoSearch(self.engine)

    async def start(self):
        print("🔍 Search Node iniciando...")
        async with websockets.connect(self.ws_url) as ws:
            self.ws = ws
            await self._send("SEARCH_NODE_ONLINE", {
                "capabilities": [
                    "web_search","social_search",
                    "geo_search","news_search",
                    "academic_search","code_search"
                ]
            })
            print("✅ Search Node conectado")
            async for msg in ws:
                await self._handle(json.loads(msg))

    async def _handle(self, msg: dict):
        event   = msg.get("event","")
        payload = msg.get("payload",{})

        if event == "SEARCH_REQUEST":
            q = SearchQuery(
                text=payload.get("query",""),
                type=payload.get("type","general"),
                max_results=payload.get("max_results",10)
            )
            result = await self.engine.search(q)
            await self._send("SEARCH_RESULT", {
                "request_id": payload.get("request_id"),
                "result":     result
            })

        elif event == "GEO_SEARCH_REQUEST":
            result = await self.geo.search_nearby(
                payload.get("query",""),
                payload.get("radius_km", 5)
            )
            await self._send("GEO_SEARCH_RESULT", {
                "request_id": payload.get("request_id"),
                "result":     result
            })

        elif event == "AME_TELEMETRY":
            gps = payload.get("gps")
            if gps:
                self.geo.update_location(
                    gps["lat"], gps["lng"],
                    gps.get("accuracy",0)
                )

    async def _send(self, event: str, payload: dict):
        await self.ws.send(json.dumps({
            "node":    "SEARCH_NODE",
            "event":   event,
            "payload": payload
        }))

if __name__ == "__main__":
    asyncio.run(SearchNode().start())