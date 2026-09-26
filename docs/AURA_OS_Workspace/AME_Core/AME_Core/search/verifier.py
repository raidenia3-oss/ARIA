import re
from typing import List
from search.aura_search import SearchResult

TRUSTED_DOMAINS = {
    ".gov": 0.98, ".edu": 0.95,
    "wikipedia.org": 0.88, "arxiv.org": 0.92,
    "github.com": 0.85, "reuters.com": 0.92,
    "bbc.com": 0.90, "who.int": 0.97,
    "pypi.org": 0.90, "npmjs.com": 0.88,
}
SUSPICIOUS = [
    r"click here", r"buy now", r"make money fast",
    r"100% free", r"limited offer",
]

class CredibilityVerifier:

    async def score_all(self,
                        results: List[SearchResult]
                        ) -> List[SearchResult]:
        for r in results:
            r.credibility = self._score(r)
        # Cross-verificación
        return self._cross_verify(results)

    def _score(self, r: SearchResult) -> float:
        score = r.credibility
        url   = r.url.lower()
        for domain, trust in TRUSTED_DOMAINS.items():
            if domain in url:
                score = max(score, trust)
                break
        text = (r.title + " " + r.snippet).lower()
        suspicious = sum(1 for p in SUSPICIOUS
                         if re.search(p, text, re.I))
        score -= suspicious * 0.1
        if not r.url or r.url == "#":
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)

    def _cross_verify(self,
                      results: List[SearchResult]
                      ) -> List[SearchResult]:
        from collections import defaultdict
        groups = defaultdict(list)
        for r in results:
            key = r.snippet[:40].lower().strip()
            if key:
                groups[key].append(r)
        for group in groups.values():
            if len(group) >= 2:
                for r in group:
                    r.credibility = min(0.99,
                                        r.credibility + 0.08)
                    r.metadata["cross_verified"] = True
                    r.metadata["sources_count"]  = len(group)
        return results