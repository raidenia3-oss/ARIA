import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List

WIKI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "second-brain", "wiki", "answers")


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    text = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _score(text: str, terms: List[str]) -> int:
    low = text.lower()
    return sum(low.count(t) for t in terms)


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    query = str(params.get("query", "")).strip()
    urls = params.get("urls") or []
    if not query:
        return {"status": "error", "error": "query vacio"}
    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 3]
    if not urls:
        search_url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        try:
            html = _fetch(search_url)
            urls = re.findall(r'href="(https?://[^"]+)"', html)[:3]
        except Exception as e:
            return {"status": "error", "error": str(e)}
    sources = []
    for url in urls[:5]:
        try:
            text = _fetch(url)
            sources.append({"url": url, "score": _score(text, terms), "excerpt": text[:500]})
        except Exception as e:
            sources.append({"url": url, "score": 0, "error": str(e)})
    sources.sort(key=lambda x: x.get("score", 0), reverse=True)
    os.makedirs(WIKI_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower())[:60].strip("-") or "research"
    path = os.path.join(WIKI_DIR, slug + ".md")
    lines = [f"# {query}", "", f"Fecha: {datetime.now().isoformat(timespec='seconds')}", "", "## Fuentes"]
    for s in sources:
        lines.append(f"- {s['url']} (score {s.get('score', 0)})")
    lines.append("")
    lines.append("## Sintesis")
    for s in sources[:3]:
        if "excerpt" in s:
            lines.append(s["excerpt"])
            lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return {"status": "ok", "query": query, "sources": len(sources), "page": path, "top_score": sources[0].get("score", 0) if sources else 0}
