import asyncio
from typing import Optional, Dict
from search.aura_search import AURASearchEngine, SearchQuery

class GeoSearch:

    def __init__(self, engine: AURASearchEngine):
        self.engine   = engine
        self.location: Optional[Dict] = None

    def update_location(self, lat: float, lng: float,
                        accuracy: float = 0):
        """AME actualiza ubicación desde GPS del celular"""
        self.location = {
            "lat": lat, "lng": lng,
            "accuracy": accuracy,
            "radius_km": max(1, accuracy/1000)
        }

    async def search_nearby(self, query: str,
                            radius_km=5) -> Dict:
        if not self.location:
            return {"error": "Sin GPS. Activa ubicación."}
        q = SearchQuery(
            text=query, type="geo",
            location={**self.location,
                      "radius_km": radius_km},
            sources=["overpass_osm","nominatim",
                     "openweather","duckduckgo"],
            max_results=10
        )
        return await self.engine.search(q)

    async def search_with_context(self, query: str) -> Dict:
        """Búsqueda enriquecida con clima y entorno"""
        if not self.location:
            return await self.engine.search(
                SearchQuery(text=query)
            )
        results = await asyncio.gather(
            self.engine.search(SearchQuery(
                text=query, type="geo",
                location=self.location
            )),
            self.engine.search(SearchQuery(
                text="clima", type="geo",
                location=self.location,
                sources=["openweather"]
            ))
        )
        return {"main": results[0],
                "weather": results[1],
                "location": self.location}