import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# --- DUCKDUCKGO (general) ---
def search_ddg(query: str, max_results=3) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        out = ""
        for r in results:
            out += f"\n[DDG] {r.get('title')}: {r.get('body')}"
        return out
    except Exception as e:
        return ""

# --- WIKIPEDIA ---
def search_wikipedia(query: str) -> str:
    try:
        url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        res = requests.get(url, headers=HEADERS, timeout=5)
        data = res.json()
        if "extract" in data:
            return f"\n[Wikipedia] {data['title']}: {data['extract'][:500]}"
        return ""
    except:
        return ""

# --- BBC NOTICIAS ---
def search_bbc() -> str:
    try:
        res = requests.get("https://feeds.bbci.co.uk/mundo/rss.xml", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")[:4]
        out = ""
        for item in items:
            title = item.find("title").text if item.find("title") else ""
            desc = item.find("description").text if item.find("description") else ""
            out += f"\n[BBC] {title}: {desc[:150]}"
        return out
    except:
        return ""

# --- TECNOLOGÍA (The Verge RSS) ---
def search_tech_news() -> str:
    try:
        res = requests.get("https://www.theverge.com/rss/index.xml", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("entry")[:3]
        out = ""
        for item in items:
            title = item.find("title").text if item.find("title") else ""
            summary = item.find("summary")
            text = BeautifulSoup(summary.text, "html.parser").get_text()[:150] if summary else ""
            out += f"\n[Tech] {title}: {text}"
        return out
    except:
        return ""

# --- ROUTER PRINCIPAL ---
def smart_search(query: str) -> str:
    q = query.lower()
    results = ""

    # Wikipedia para definiciones/conceptos
    if any(k in q for k in ["qué es", "que es", "quien es", "quién es", "historia", "definición", "definicion"]):
        results += search_wikipedia(query)

    # BBC para noticias
    if any(k in q for k in ["noticia", "noticias", "hoy", "mundial", "política", "politica", "guerra", "economía"]):
        results += search_bbc()

    # Tech news
    if any(k in q for k in ["tecnología", "tecnologia", "ia", "inteligencia artificial", "gpu", "cpu", "nvidia", "apple", "google", "microsoft"]):
        results += search_tech_news()

    # DDG siempre como complemento
    results += search_ddg(query)

    return results if results else ""
