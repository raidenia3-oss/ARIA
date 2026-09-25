import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    query = params.get("query", "")
    if not query:
        return {"results": [], "error": "query vacío"}
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
        results = []
        for line in html.splitlines():
            if "result__a" in line and "href=" in line:
                results.append(line.strip())
            if len(results) >= 5:
                break
        return {"query": query, "results": results, "count": len(results)}
    except urllib.error.URLError as e:
        return {"query": query, "results": [], "error": str(e)}
    except Exception as e:
        return {"query": query, "results": [], "error": str(e)}
