import os, requests
from typing import List
from search.aura_search import SearchResult

class ResultSynthesizer:

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY","")

    async def synthesize(self, query: str,
                         results: List[SearchResult]) -> str:
        if self.api_key:
            return self._gemini(query, results)
        return self._simple(query, results)

    def _gemini(self, query: str,
                results: List[SearchResult]) -> str:
        context = "\n\n".join([
            f"[{i+1}] {r.source.upper()} "
            f"(confiabilidad: {r.credibility})\n"
            f"Título: {r.title}\n"
            f"Contenido: {r.snippet}"
            for i, r in enumerate(results[:6])
        ])
        prompt = (
            f"Sintetiza una respuesta clara sobre: '{query}'\n\n"
            f"FUENTES:\n{context}\n\n"
            f"Responde en español, cita fuentes con [N], "
            f"máximo 200 palabras, sé objetivo y factual."
        )
        try:
            url = ("https://generativelanguage.googleapis.com"
                   "/v1beta/models/gemini-1.5-flash"
                   ":generateContent")
            r = requests.post(
                url, params={"key": self.api_key},
                json={"contents":[{"parts":[{"text":prompt}]}]},
                timeout=15
            )
            return (r.json()["candidates"][0]
                    ["content"]["parts"][0]["text"])
        except Exception:
            return self._simple(query, results)

    def _simple(self, query: str,
                results: List[SearchResult]) -> str:
        if not results:
            return f"Sin resultados para: {query}"
        lines = [f"🔍 {query}\n"]
        for i, r in enumerate(results[:3], 1):
            icon = ("🟢" if r.credibility >= 0.8 else
                    "🟡" if r.credibility >= 0.6 else "🔴")
            lines.append(
                f"[{i}] {icon} {r.source.upper()}\n"
                f"    {r.title}\n"
                f"    {r.snippet[:150]}...\n"
            )
        cross = [r for r in results
                 if r.metadata.get("cross_verified")]
        if cross:
            lines.append(
                f"✅ {len(cross)} resultado(s) "
                f"verificados en múltiples fuentes"
            )
        return "\n".join(lines)