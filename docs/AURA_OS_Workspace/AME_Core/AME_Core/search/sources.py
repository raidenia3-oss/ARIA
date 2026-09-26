import re, json
import aiohttp
from bs4 import BeautifulSoup
from typing import List
from search.aura_search import SearchResult, SearchQuery
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AURABot/1.0)",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

class SourceRegistry:

    async def search(self, source: str,
                     query: SearchQuery) -> List[SearchResult]:
        handlers = {
            "duckduckgo":      self._duckduckgo,
            "bing":            self._bing,
            "reddit":          self._reddit,
            "twitter_nitter":  self._nitter,
            "youtube_public":  self._youtube,
            "github":          self._github,
            "arxiv":           self._arxiv,
            "overpass_osm":    self._osm,
            "nominatim":       self._nominatim,
            "openweather":     self._weather,
            "google_news_rss": self._google_news,
            "mastodon":        self._mastodon,
            "pypi":            self._pypi,
            "npm_registry":    self._npm,
        }
        handler = handlers.get(source)
        if not handler:
            return []
        try:
            async with aiohttp.ClientSession(
                headers=HEADERS
            ) as session:
                return await handler(session, query)
        except Exception as e:
            print(f"   ❌ {source}: {e}")
            return []

    async def _duckduckgo(self, s, q):
        url = "https://api.duckduckgo.com/"
        params = {"q": q.text, "format": "json",
                  "no_html": 1, "skip_disambig": 1}
        async with s.get(url, params=params) as r:
            data = await r.json(content_type=None)
        results = []
        if data.get("AbstractText"):
            results.append(SearchResult(
                title=data.get("Heading","DDG"),
                url=data.get("AbstractURL",""),
                snippet=data["AbstractText"][:400],
                source="duckduckgo", credibility=0.8,
                timestamp=datetime.now().isoformat(),
                metadata={"type":"instant_answer"}
            ))
        for item in data.get("RelatedTopics",[])[:6]:
            if "Text" in item and "FirstURL" in item:
                results.append(SearchResult(
                    title=item["Text"][:80],
                    url=item["FirstURL"],
                    snippet=item["Text"][:300],
                    source="duckduckgo", credibility=0.7,
                    timestamp=datetime.now().isoformat()
                ))
        return results

    async def _bing(self, s, q):
        url = f"https://www.bing.com/search?q={q.text}&count=8"
        async with s.get(url) as r:
            html = await r.text()
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for li in soup.select(".b_algo")[:6]:
            h = li.select_one("h2 a")
            p = li.select_one(".b_caption p")
            if h:
                results.append(SearchResult(
                    title=h.get_text()[:100],
                    url=h.get("href",""),
                    snippet=p.get_text()[:300] if p else "",
                    source="bing", credibility=0.75,
                    timestamp=datetime.now().isoformat()
                ))
        return results

    async def _reddit(self, s, q):
        url = (f"https://www.reddit.com/search.json"
               f"?q={q.text}&limit=6&sort=relevance")
        async with s.get(url) as r:
            data = await r.json()
        results = []
        for post in data.get("data",{}).get("children",[]):
            p = post["data"]
            cred = min(0.85,
                0.4 + min(p.get("score",0),10000)/30000
                + p.get("upvote_ratio",0.5)*0.2
            )
            results.append(SearchResult(
                title=p.get("title","")[:100],
                url=f"https://reddit.com{p.get('permalink','')}",
                snippet=p.get("selftext","")[:300],
                source="reddit", credibility=cred,
                timestamp=datetime.fromtimestamp(
                    p.get("created_utc",0)
                ).isoformat(),
                metadata={
                    "subreddit": p.get("subreddit",""),
                    "score":     p.get("score",0)
                }
            ))
        return results

    async def _nitter(self, s, q):
        """Twitter público via instancias Nitter abiertas"""
        instances = [
            "https://nitter.net",
            "https://nitter.it",
            "https://nitter.1d4.us",
        ]
        for base in instances:
            try:
                url = f"{base}/search?q={q.text}&f=tweets"
                async with s.get(url, timeout=8) as r:
                    if r.status != 200:
                        continue
                    html = await r.text()
                soup = BeautifulSoup(html, "html.parser")
                results = []
                for tw in soup.select(".tweet-content")[:6]:
                    parent = tw.find_parent(
                        class_="timeline-item"
                    )
                    user = ""
                    if parent:
                        u = parent.select_one(".username")
                        user = u.get_text() if u else ""
                    results.append(SearchResult(
                        title=f"@{user}",
                        url=base,
                        snippet=tw.get_text()[:300],
                        source="twitter_public",
                        credibility=0.5,
                        timestamp=datetime.now().isoformat(),
                        metadata={"platform":"twitter"}
                    ))
                if results:
                    return results
            except Exception:
                continue
        return []

    async def _youtube(self, s, q):
        url = (f"https://www.youtube.com/results"
               f"?search_query={q.text}")
        async with s.get(url) as r:
            html = await r.text()
        match = re.search(
            r'var ytInitialData = ({.*?});', html, re.DOTALL
        )
        results = []
        if not match:
            return results
        try:
            data  = json.loads(match.group(1))
            items = (data.get("contents",{})
                     .get("twoColumnSearchResultsRenderer",{})
                     .get("primaryContents",{})
                     .get("sectionListRenderer",{})
                     .get("contents",[]))
            for section in items:
                for item in (section
                    .get("itemSectionRenderer",{})
                    .get("contents",[]))[:5]:
                    v = item.get("videoRenderer",{})
                    if v:
                        vid = v.get("videoId","")
                        ttl = (v.get("title",{})
                                .get("runs",[{}])[0]
                                .get("text",""))
                        results.append(SearchResult(
                            title=ttl[:100],
                            url=f"https://youtube.com/watch?v={vid}",
                            snippet="",
                            source="youtube",
                            credibility=0.65,
                            timestamp=datetime.now().isoformat(),
                            metadata={"video_id": vid}
                        ))
        except Exception:
            pass
        return results

    async def _github(self, s, q):
        url = "https://api.github.com/search/repositories"
        params = {"q": q.text, "sort":"stars", "per_page":5}
        async with s.get(url, params=params) as r:
            data = await r.json()
        results = []
        for repo in data.get("items",[]):
            stars = repo.get("stargazers_count",0)
            cred  = min(0.95, 0.5 + min(stars,10000)/20000)
            results.append(SearchResult(
                title=repo.get("full_name",""),
                url=repo.get("html_url",""),
                snippet=repo.get("description","")[:300],
                source="github", credibility=cred,
                timestamp=repo.get("updated_at",""),
                metadata={
                    "stars":    stars,
                    "language": repo.get("language","")
                }
            ))
        return results

    async def _arxiv(self, s, q):
        url = "https://export.arxiv.org/api/query"
        params = {"search_query": f"all:{q.text}",
                  "max_results": 5}
        async with s.get(url, params=params) as r:
            xml = await r.text()
        entries = re.findall(
            r'<entry>(.*?)</entry>', xml, re.DOTALL
        )
        results = []
        for e in entries[:5]:
            title = re.search(r'<title>(.*?)</title>', e)
            summ  = re.search(
                r'<summary>(.*?)</summary>', e, re.DOTALL
            )
            link  = re.search(r'<id>(.*?)</id>', e)
            if title:
                results.append(SearchResult(
                    title=title.group(1).strip()[:100],
                    url=link.group(1).strip() if link else "",
                    snippet=summ.group(1).strip()[:300] if summ else "",
                    source="arxiv", credibility=0.92,
                    timestamp=datetime.now().isoformat(),
                    metadata={"type":"academic"}
                ))
        return results

    async def _osm(self, s, q):
        if not q.location:
            return []
        lat = q.location.get("lat",0)
        lng = q.location.get("lng",0)
        rad = q.location.get("radius_km",5)*1000
        overpass_q = f"""
        [out:json][timeout:15];
        (node(around:{rad},{lat},{lng})["name"~"{q.text}",i];
         way(around:{rad},{lat},{lng})["name"~"{q.text}",i];);
        out center 8;"""
        url = "https://overpass-api.de/api/interpreter"
        async with s.post(url, data=overpass_q) as r:
            data = await r.json()
        results = []
        for el in data.get("elements",[])[:6]:
            tags = el.get("tags",{})
            results.append(SearchResult(
                title=tags.get("name","Lugar"),
                url=f"https://openstreetmap.org/node/{el.get('id','')}",
                snippet=", ".join(
                    f"{k}:{v}" for k,v in tags.items()
                    if k != "name"
                )[:200],
                source="openstreetmap", credibility=0.85,
                timestamp=datetime.now().isoformat(),
                metadata={"tags": tags,
                          "lat": el.get("lat"),
                          "lng": el.get("lon")}
            ))
        return results

    async def _nominatim(self, s, q):
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": q.text, "format":"json",
                  "limit":5, "addressdetails":1}
        async with s.get(url, params=params) as r:
            data = await r.json()
        return [SearchResult(
            title=p.get("display_name","")[:100],
            url="https://openstreetmap.org",
            snippet=json.dumps(p.get("address",{}))[:200],
            source="nominatim", credibility=0.88,
            timestamp=datetime.now().isoformat(),
            metadata={"lat":p.get("lat"),"lng":p.get("lon")}
        ) for p in data[:5]]

    async def _weather(self, s, q):
        if not q.location:
            return []
        url = "https://wttr.in/"
        params = {
            "lat": q.location.get("lat"),
            "lon": q.location.get("lng"),
            "format": "j1"
        }
        async with s.get(url, params=params) as r:
            data = await r.json()
        cur = data.get("current_condition",[{}])[0]
        return [SearchResult(
            title="Clima actual",
            url="https://wttr.in",
            snippet=(f"Temp: {cur.get('temp_C','?')}°C | "
                     f"Humedad: {cur.get('humidity','?')}% | "
                     f"{cur.get('weatherDesc',[{}])[0].get('value','')}"),
            source="weather", credibility=0.9,
            timestamp=datetime.now().isoformat(),
            metadata={"weather": cur}
        )]

    async def _google_news(self, s, q):
        url = (f"https://news.google.com/rss/search"
               f"?q={q.text}&hl=es&gl=ES&ceid=ES:es")
        async with s.get(url) as r:
            xml = await r.text()
        items = re.findall(r'<item>(.*?)</item>',
                           xml, re.DOTALL)
        results = []
        for item in items[:6]:
            title = re.search(r'<title>(.*?)</title>', item)
            link  = re.search(r'<link/>(.*?)\n', item)
            pub   = re.search(r'<pubDate>(.*?)</pubDate>', item)
            if title:
                results.append(SearchResult(
                    title=re.sub(r'<[^>]+>','',
                                 title.group(1))[:100],
                    url=link.group(1).strip() if link else "",
                    snippet="",
                    source="google_news",
                    credibility=0.82,
                    timestamp=pub.group(1) if pub else "",
                    metadata={"type":"news"}
                ))
        return results

    async def _mastodon(self, s, q):
        url = "https://mastodon.social/api/v2/search"
        params = {"q":q.text,"type":"statuses","limit":5}
        async with s.get(url, params=params) as r:
            data = await r.json()
        results = []
        for st in data.get("statuses",[]):
            soup = BeautifulSoup(st.get("content",""),
                                 "html.parser")
            results.append(SearchResult(
                title=f"@{st.get('account',{}).get('username','')}",
                url=st.get("url",""),
                snippet=soup.get_text()[:300],
                source="mastodon", credibility=0.5,
                timestamp=st.get("created_at",""),
                metadata={"favourites":
                          st.get("favourites_count",0)}
            ))
        return results

    async def _pypi(self, s, q):
        url = f"https://pypi.org/pypi/{q.text}/json"
        async with s.get(url) as r:
            if r.status != 200:
                return []
            data = await r.json()
        info = data.get("info",{})
        return [SearchResult(
            title=f"{info.get('name','')} v{info.get('version','')}",
            url=info.get("project_url",""),
            snippet=info.get("summary","")[:300],
            source="pypi", credibility=0.9,
            timestamp=datetime.now().isoformat(),
            metadata={"version":info.get("version"),
                      "author":info.get("author")}
        )]

    async def _npm(self, s, q):
        url = (f"https://registry.npmjs.org/-/v1/search"
               f"?text={q.text}&size=5")
        async with s.get(url) as r:
            data = await r.json()
        results = []
        for pkg in data.get("objects",[]):
            p = pkg.get("package",{})
            results.append(SearchResult(
                title=f"{p.get('name','')} v{p.get('version','')}",
                url=p.get("links",{}).get("npm",""),
                snippet=p.get("description","")[:300],
                source="npm", credibility=0.88,
                timestamp=p.get("date",""),
                metadata={"version":p.get("version")}
            ))
        return results