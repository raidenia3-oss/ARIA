import asyncio, aiohttp, json, re
from typing import List, Dict
from datetime import datetime
from search.aura_search import SearchResult, SearchQuery

HEADERS = {
    "User-Agent": "AURA-Security-Research/1.0 (legit audit tool)"
}

class TechIntelSource:
    """
    Fuentes oficiales de inteligencia técnica.
    Todas son públicas y legítimas para investigación
    de seguridad y auditoría de sistemas propios.
    """

    async def search(self, source: str,
                     query: SearchQuery) -> List[SearchResult]:
        handlers = {
            "nvd_cve":    self._nvd_cve,
            "exploit_db": self._exploit_db,
            "gh_advisory": self._github_advisory,
            "shodan_free": self._shodan_public,
        }
        handler = handlers.get(source)
        if not handler:
            return []
        try:
            async with aiohttp.ClientSession(
                headers=HEADERS
            ) as s:
                return await handler(s, query)
        except Exception as e:
            print(f"❌ {source}: {e}")
            return []

    async def _nvd_cve(self, s, q) -> List[SearchResult]:
        """
        NVD NIST — Base de datos oficial de CVEs
        del gobierno de Estados Unidos. Completamente pública.
        https://nvd.nist.gov/developers/vulnerabilities
        """
        url = ("https://services.nvd.nist.gov"
               "/rest/json/cves/2.0")
        params = {
            "keywordSearch":  q.text,
            "resultsPerPage": 6
        }
        async with s.get(url, params=params,
                         timeout=15) as r:
            data = await r.json()

        results = []
        for vuln in data.get("vulnerabilities",[]):
            cve  = vuln.get("cve",{})
            desc = (cve.get("descriptions",[{}])[0]
                       .get("value",""))
            # CVSS score para determinar severidad
            metrics = cve.get("metrics",{})
            cvss_v3 = (metrics.get("cvssMetricV31",[{}])
                              [0].get("cvssData",{}))
            score = cvss_v3.get("baseScore", 0)
            severity = (
                "CRITICAL" if score >= 9.0 else
                "HIGH"     if score >= 7.0 else
                "MEDIUM"   if score >= 4.0 else
                "LOW"      if score >  0   else "NONE"
            )
            results.append(SearchResult(
                title=cve.get("id",""),
                url=(f"https://nvd.nist.gov/vuln/detail/"
                     f"{cve.get('id','')}"),
                snippet=desc[:300],
                source="nvd_nist",
                credibility=0.99,  # Fuente gubernamental oficial
                timestamp=cve.get("published",""),
                metadata={
                    "cvss_score": score,
                    "severity":   severity,
                    "vector":     cvss_v3.get("vectorString",""),
                    "cve_id":     cve.get("id","")
                }
            ))
        return results

    async def _exploit_db(self, s, q) -> List[SearchResult]:
        """
        Exploit-DB — Base de datos pública de exploits
        conocidos, mantenida por Offensive Security.
        Uso legítimo: verificar si tu sistema es vulnerable.
        https://www.exploit-db.com
        """
        url = "https://www.exploit-db.com/search"
        params = {
            "draw":               1,
            "search[value]":      q.text,
            "length":             6,
            "columns[0][data]":   "date_published"
        }
        headers = {
            **HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json"
        }
        async with s.get(url, params=params,
                         headers=headers) as r:
            data = await r.json()

        results = []
        for item in data.get("data",[])[:6]:
            results.append(SearchResult(
                title=item.get("description","")[:100],
                url=(f"https://www.exploit-db.com"
                     f"/exploits/{item.get('id','')}"),
                snippet=(
                    f"Plataforma: {item.get('platform','')} | "
                    f"Tipo: {item.get('type','')} | "
                    f"Autor: {item.get('author','')}"
                ),
                source="exploit_db",
                credibility=0.85,
                timestamp=item.get("date_published",""),
                metadata={
                    "platform": item.get("platform",""),
                    "type":     item.get("type",""),
                    "edb_id":   item.get("id","")
                }
            ))
        return results

    async def _github_advisory(self, s, q) -> List[SearchResult]:
        """
        GitHub Advisory Database — vulnerabilidades en
        librerías open source. API pública oficial.
        https://github.com/advisories
        """
        url = "https://api.github.com/advisories"
        params = {"q": q.text, "per_page": 6}
        async with s.get(url, params=params) as r:
            if r.status != 200:
                return []
            data = await r.json()

        results = []
        for advisory in (data if isinstance(data, list)
                         else [])[:6]:
            severity = advisory.get("severity","unknown")
            cred = {
                "critical": 0.95, "high": 0.90,
                "medium": 0.85, "low": 0.80
            }.get(severity.lower(), 0.75)
            results.append(SearchResult(
                title=advisory.get("summary","")[:100],
                url=advisory.get("html_url",""),
                snippet=advisory.get("description","")[:300],
                source="github_advisory",
                credibility=cred,
                timestamp=advisory.get("published_at",""),
                metadata={
                    "severity":  severity,
                    "ghsa_id":   advisory.get("ghsa_id",""),
                    "ecosystem": (advisory.get(
                        "vulnerabilities",[{}]
                    )[0].get("package",{})
                     .get("ecosystem","") if advisory.get(
                        "vulnerabilities") else "")
                }
            ))
        return results

    async def _shodan_public(self, s, q) -> List[SearchResult]:
        """
        Shodan — información pública de dispositivos en internet.
        Solo resultados públicos visibles sin autenticación.
        Uso legítimo: verificar exposición de tus propios servicios.
        https://www.shodan.io
        """
        from bs4 import BeautifulSoup
        url = f"https://www.shodan.io/search?query={q.text}"
        async with s.get(url) as r:
            if r.status != 200:
                return []
            html = await r.text()

        soup = BeautifulSoup(html, "html.parser")
        results = []
        for result in soup.select(".result")[:5]:
            ip_el   = result.select_one(".ip")
            port_el = result.select_one(".port")
            org_el  = result.select_one(".org")
            if ip_el:
                ip = ip_el.get_text().strip()
                results.append(SearchResult(
                    title=f"Host: {ip}",
                    url=f"https://www.shodan.io/host/{ip}",
                    snippet=(
                        f"Puerto: {port_el.get_text().strip() if port_el else '?'} | "
                        f"Organización: {org_el.get_text().strip() if org_el else '?'}"
                    ),
                    source="shodan_public",
                    credibility=0.88,
                    timestamp=datetime.now().isoformat(),
                    metadata={"ip": ip}
                ))
        return results

class TechIntelNode:
    """
    Nodo de inteligencia técnica conectado al EventBus.
    Responde a peticiones de investigación de seguridad
    sobre la propia infraestructura AURA/AME.
    """

    def __init__(self, ws_url="ws://localhost:8765"):
        self.ws_url = ws_url
        self.intel  = TechIntelSource()
        self.ws     = None

    async def start(self):
        import websockets
        print("🛡️  Tech Intel Node iniciando...")
        async with websockets.connect(self.ws_url) as ws:
            self.ws = ws
            await self._send("TECH_INTEL_ONLINE", {
                "capabilities": [
                    "cve_lookup",
                    "exploit_search",
                    "advisory_lookup",
                    "host_info"
                ],
                "note": ("Solo para auditoría de "
                         "infraestructura propia")
            })
            print("✅ Tech Intel Node conectado")
            async for msg in ws:
                await self._handle(json.loads(msg))

    async def _handle(self, msg: dict):
        event   = msg.get("event","")
        payload = msg.get("payload",{})

        if event == "CVE_LOOKUP":
            # Buscar CVEs para un software/versión específica
            results = await self.intel.search(
                "nvd_cve",
                SearchQuery(text=payload.get("query",""))
            )
            await self._send("CVE_RESULTS", {
                "request_id": payload.get("request_id"),
                "results":    [self._fmt(r) for r in results],
                "count":      len(results)
            })

        elif event == "ADVISORY_LOOKUP":
            # Buscar advisories para dependencias del proyecto
            results = await self.intel.search(
                "gh_advisory",
                SearchQuery(text=payload.get("package",""))
            )
            await self._send("ADVISORY_RESULTS", {
                "request_id": payload.get("request_id"),
                "results":    [self._fmt(r) for r in results]
            })

        elif event == "VULN_SCANNER_COMPLETE":
            # VULN_SCANNER encontró un servicio →
            # buscar CVEs automáticamente
            service = payload.get("service","")
            version = payload.get("version","")
            if service:
                query = f"{service} {version} vulnerability"
                results = await self.intel.search(
                    "nvd_cve",
                    SearchQuery(text=query)
                )
                await self._send("AUTO_CVE_ENRICHMENT", {
                    "service": service,
                    "version": version,
                    "cves":    [self._fmt(r) for r in results]
                })

    def _fmt(self, r: SearchResult) -> Dict:
        return {
            "title":       r.title,
            "url":         r.url,
            "snippet":     r.snippet,
            "source":      r.source,
            "credibility": r.credibility,
            "metadata":    r.metadata
        }

    async def _send(self, event: str, payload: dict):
        if self.ws:
            await self.ws.send(json.dumps({
                "node":    "TECH_INTEL_NODE",
                "event":   event,
                "payload": payload
            }))

if __name__ == "__main__":
    asyncio.run(TechIntelNode().start())