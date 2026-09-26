import asyncio, json, time, hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class SearchResult:
    title:       str
    url:         str
    snippet:     str
    source:      str
    credibility: float
    timestamp:   str
    metadata:    Dict = field(default_factory=dict)

@dataclass
class SearchQuery:
    text:        str
    type:        str  = "general"
    location:    Optional[Dict] = None
    sources:     List[str] = field(default_factory=list)
    max_results: int  = 20
    verify:      bool = True

class AURASearchEngine:

    def __init__(self):
        from search.sources   import SourceRegistry
        from search.verifier  import CredibilityVerifier
        from search.synthesizer import ResultSynthesizer
        self.sources     = SourceRegistry()
        self.verifier    = CredibilityVerifier()
        self.synthesizer = ResultSynthesizer()
        self.cache       = SearchCache()

    async def search(self, query: SearchQuery) -> Dict:
        start = time.time()

        # Caché
        key = self.cache.key(query)
        if cached := self.cache.get(key):
            cached["from_cache"] = True
            return cached

        # Seleccionar fuentes
        sources = self._select_sources(query)
        print(f"🔍 Buscando: '{query.text}'")
        print(f"   Fuentes: {', '.join(sources)}")

        # Buscar en paralelo
        tasks = [self.sources.search(s, query) for s in sources]
        raw   = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: List[SearchResult] = []
        for i, res in enumerate(raw):
            if isinstance(res, Exception):
                print(f"   ⚠️ {sources[i]}: {res}")
            elif res:
                all_results.extend(res)

        if not all_results:
            return {"error": "Sin resultados", "query": query.text}

        if query.verify:
            all_results = await self.verifier.score_all(all_results)

        all_results.sort(
            key=lambda r: (r.credibility,
                           self._relevance(r, query)),
            reverse=True
        )
        all_results = all_results[:query.max_results]

        synthesis = await self.synthesizer.synthesize(
            query.text, all_results
        )

        result = {
            "query":       query.text,
            "type":        query.type,
            "total_found": len(all_results),
            "sources_used": sources,
            "elapsed_ms":  round((time.time()-start)*1000),
            "synthesis":   synthesis,
            "results":     [self._fmt(r) for r in all_results],
            "timestamp":   datetime.now().isoformat()
        }
        self.cache.set(key, result)
        return result

    def _select_sources(self, query: SearchQuery) -> List[str]:
        if query.sources:
            return query.sources
        text = query.text.lower()

        if query.type == "tech":
            return ["duckduckgo","github","stackoverflow",
                    "arxiv","pypi","npm_registry"]

        if query.type == "geo" or query.location:
            return ["overpass_osm","nominatim",
                    "openweather","duckduckgo"]

        if query.type == "news":
            return ["google_news_rss","reddit",
                    "mastodon","duckduckgo"]

        if query.type == "social":
            return ["reddit","mastodon","youtube_public",
                    "twitter_nitter"]

        # Detección automática
        sources = ["duckduckgo", "bing"]

        if any(w in text for w in
               ["noticias","news","hoy","tendencia"]):
            sources += ["google_news_rss","reddit"]

        if any(w in text for w in
               ["video","youtube","canal"]):
            sources += ["youtube_public"]

        if any(w in text for w in
               ["codigo","code","repo","libreria","library"]):
            sources += ["github","pypi","npm_registry"]

        if any(w in text for w in
               ["cerca","near","zona","lugar","ciudad"]):
            sources += ["overpass_osm","nominatim"]

        if any(w in text for w in
               ["paper","investigacion","estudio","academic"]):
            sources += ["arxiv","duckduckgo"]

        return list(dict.fromkeys(sources))

    def _relevance(self, r: SearchResult,
                   q: SearchQuery) -> float:
        kws  = q.text.lower().split()
        text = (r.title + " " + r.snippet).lower()
        hits = sum(1 for kw in kws if kw in text)
        return hits / max(len(kws), 1)

    def _fmt(self, r: SearchResult) -> Dict:
        return {
            "title":       r.title,
            "url":         r.url,
            "snippet":     r.snippet[:300],
            "source":      r.source,
            "credibility": round(r.credibility, 2),
            "timestamp":   r.timestamp,
            "metadata":    r.metadata
        }

class SearchCache:
    def __init__(self, ttl_minutes=15):
        self._cache: Dict = {}
        self._ttl   = ttl_minutes * 60

    def key(self, q: SearchQuery) -> str:
        raw = f"{q.text}:{q.type}:{q.location}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[Dict]:
        if key in self._cache:
            e = self._cache[key]
            if time.time() - e["ts"] < self._ttl:
                return e["data"]
            del self._cache[key]
        return None

    def set(self, key: str, data: Dict):
        self._cache[key] = {"data": data, "ts": time.time()}
        if len(self._cache) > 200:
            oldest = min(self._cache,
                         key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest]