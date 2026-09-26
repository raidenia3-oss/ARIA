#!/usr/bin/env python3
"""
AURA Knowledge Collector — Recolecta datos de entrenamiento desde internet.

Busca topics en la web, extrae contenido de artículos/páginas y genera
pares Pregunta/Respuesta en formato JSONL listos para fine-tuning.

Fuentes de búsqueda (fallback automático):
  1. Wikipedia API    (gratuita, confiable)
  2. Gemini Search API  (requiere GEMINI_API_KEY)
  3. Bing HTML scrape    (sin key)
  4. DuckDuckGo scrape   (sin key)
  5. Dogpile scrape      (fallback)

Uso:
  python scripts/aura_web_collector.py --topics "AURA AI,LLM fine-tuning" --count 50
  python scripts/aura_web_collector.py --query "Python async programming" --count 20
  python scripts/aura_web_collector.py --from-wiki "Qwen" --count 30
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import random
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import quote_plus, urljoin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("AuraWebCollector")

USER_AGENT = "AURA-KnowledgeCollector/1.0 (educational research bot)"


class WebFetcher:
    """Fetch + clean text content from web pages."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        try:
            import httpx
            self.httpx = httpx
        except ImportError:
            import urllib.request
            self.httpx = None
            self._urllib = urllib.request

    def get(self, url: str) -> Optional[str]:
        """Fetch raw HTML from a URL."""
        if self.httpx:
            try:
                resp = self.httpx.get(
                    url,
                    timeout=self.timeout,
                    headers={"User-Agent": USER_AGENT},
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    return resp.text
                logger.warning(f"HTTP {resp.status_code} for {url}")
            except Exception as e:
                logger.debug(f"httpx error {url}: {e}")
        else:
            try:
                req = self._urllib.Request(url, headers={"User-Agent": USER_AGENT})
                with self._urllib.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                logger.debug(f"urllib error {url}: {e}")
        return None

    def extract_text(self, html: str) -> str:
        """Extract main text content from HTML, removing boilerplate."""
        # Remove script/style blocks
        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags but preserve text
        text = re.sub(r"<[^>]+>", " ", html)
        # Clean whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text


class SearchEngine:
    """
    Busca en internet usando múltiples proveedores con fallback automatico.
    Prioridad: Wikipedia API (mas confiable) -> Bing -> DuckDuckGo -> Gemini.
    """

    WIKI_UA = "AURAKnowledgeCollector/1.0 (research bot; contact@example.com)"
    BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self, fetcher: WebFetcher, hf_token: Optional[str] = None):
        self.fetcher = fetcher
        self.hf_token = hf_token or os.getenv("HF_TOKEN", "")
        self.headers = {"User-Agent": self.BROWSER_UA}

    def search_ddg(self, query: str, num_results: int = 5) -> List[str]:
        """Searches DuckDuckGo HTML (no API key needed)."""
        try:
            import httpx
            encoded = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            resp = httpx.get(
                url, timeout=20,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            )
            if resp.status_code != 200:
                return []
            results = re.findall(
                r'href="(https?://[^"]+)"[^>]*class="result__a"', resp.text
            )
            if not results:
                results = re.findall(
                    r'<a rel="nofollow" class="result__a" href="(https?://[^"]+)"', resp.text
                )
            return [r for r in results if "duckduckgo" not in r][:num_results]
        except Exception as e:
            logger.debug(f"DuckDuckGo search failed: {e}")
            return []

    def search_bing(self, query: str, num_results: int = 5) -> List[str]:
        """Searches Bing HTML (more reliable scraper)."""
        try:
            import httpx
            encoded = quote_plus(query)
            url = f"https://www.bing.com/search?q={encoded}&count={num_results}"
            resp = httpx.get(
                url, timeout=20,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            )
            if resp.status_code != 200:
                return []
            results = re.findall(r'href="(https?://[^"]+)"', resp.text)
            clean = [r for r in results if not any(b in r for b in ["bing.com", "microsoft.com", "go.microsoft"])]
            return list(dict.fromkeys(clean))[:num_results]
        except Exception as e:
            logger.debug(f"Bing search failed: {e}")
            return []

    def search_dogpile(self, query: str, num_results: int = 5) -> List[str]:
        """Searches Dogpile as fallback."""
        try:
            import httpx
            encoded = quote_plus(query)
            url = f"https://www.dogpile.com/search?qc=web&q={encoded}"
            resp = httpx.get(
                url, timeout=20,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            )
            results = re.findall(r'href="(https?://[^"]+)"', resp.text)
            clean = [r for r in results if "dogpile" not in r and "aol" not in r]
            return list(dict.fromkeys(clean))[:num_results]
        except Exception:
            return []

    def search_wiki_api(self, query: str, num_results: int = 3) -> List[str]:
        """Wikipedia API como fuente confiable de conocimiento."""
        try:
            import httpx
            encoded = quote_plus(query)
            api_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&srlimit={num_results}&format=json"
            resp = httpx.get(api_url, timeout=15, headers={"User-Agent": self.WIKI_UA})
            if resp.status_code != 200:
                return []
            data = resp.json()
            base = "https://en.wikipedia.org/wiki/"
            return [base + s["title"].replace(" ", "_") for s in data.get("query", {}).get("search", [])]
        except Exception as e:
            logger.debug(f"Wikipedia API failed: {e}")
            return []

    def search_gemini(self, query: str, num_results: int = 3) -> List[str]:
        """Usa Gemini API como buscador de URLs (si está disponible)."""
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return []
        try:
            import requests
            base = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
            url = f"{base}/models/gemini-2.0-flash:generateContent?key={key}"
            prompt = (
                f"Return {num_results} working URLs about '{query}'. "
                f"Answer ONLY with a numbered list of URLs, one per line."
            )
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=20,
            )
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return re.findall(r"https?://[^\s<>\"'\]\)]+", text)[:num_results]
        except Exception as e:
            logger.debug(f"Gemini search failed: {e}")
            return []

    def search(self, query: str, num_results: int = 5) -> List[str]:
        """Busca con fallback: Wikipedia API → Bing → DuckDuckGo → Dogpile → Gemini."""
        urls = self.search_wiki_api(query, num_results)
        if urls:
            logger.info(f"  [Wikipedia] {len(urls)} resultados")
            return urls
        urls = self.search_bing(query, num_results)
        if urls:
            logger.info(f"  [Bing] {len(urls)} resultados")
            return urls
        urls = self.search_ddg(query, num_results)
        if urls:
            logger.info(f"  [DuckDuckGo] {len(urls)} resultados")
            return urls
        urls = self.search_dogpile(query, num_results)
        if urls:
            logger.info(f"  [Dogpile] {len(urls)} resultados")
            return urls
        urls = self.search_gemini(query, num_results)
        if urls:
            logger.info(f"  [Gemini] {len(urls)} resultados")
            return urls
        return []


class QAgenerator:
    """
    Genera pares Pregunta/Respuesta a partir de texto extraído.

    Técnica: extrae frases clave y oraciones, luego usa heurísticas
    para generar preguntas. Si se proporciona un modelo local o API key,
    usa un LLM para generar preguntas más naturales.
    """

    def __init__(self, llm_provider: Optional[str] = None):
        self.llm_provider = llm_provider

    def generate_from_text(self, text: str, source_url: str, max_pairs: int = 10) -> List[Dict]:
        """Genera pares Q&A a partir de texto."""
        if len(text) < 200:
            return []

        # Split into sentences
        sentences = re.split(r"(?<=[.!?。？！])\s+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if self.llm_provider == "local" and self._try_llm_qa(sentences, source_url, max_pairs):
            return self._last_llm_results or []

        # Heuristic approach: extract key facts
        return self._heuristic_qa(sentences, source_url, max_pairs)

    def _last_llm_results(self):
        return []

    def _try_llm_qa(self, sentences, url, max_pairs):
        """Intenta usar un LLM local o API para generar Q&A."""
        return False  # Fallback a heurística si no hay LLM

    def _heuristic_qa(self, sentences: List[str], source_url: str, max_pairs: int) -> List[Dict]:
        """Genera preguntas usando heurísticas sobre el texto."""
        results = []

        for sentence in sentences[:100]:
            sentence = sentence.strip()
            if not self._is_quality_sentence(sentence):
                continue

            q = self._reverse_to_question(sentence)
            if q and len(q) > 5:
                a = sentence
                if self._is_quality_qa(q, a):
                    results.append({
                        "text": q,
                        "output": a,
                        "metadata": {
                            "source": "web_scrape",
                            "url": source_url,
                            "timestamp": datetime.now().isoformat(),
                            "method": "heuristic",
                        },
                    })
                    if len(results) >= max_pairs:
                        break

        return results

    def _is_quality_sentence(self, sentence: str) -> bool:
        """Filtra oraciones de baja calidad (cortas, sin sustancia, markup)."""
        if len(sentence) < 60 or len(sentence) > 500:
            return False
        # Skip references, markup, navigation
        if sentence.startswith(("Figure", "Table", "Ref", "Note:", "File:", "Category:", "#", "|", "{")):
            return False
        # Skip very short sentences or those with too many markup chars
        if sentence.count("{") > 2 or sentence.count("|") > 2:
            return False
        # Must contain at least some alphabetic content
        alpha_ratio = sum(1 for c in sentence if c.isalpha()) / len(sentence)
        if alpha_ratio < 0.5:
            return False
        # Skip if it looks like a citation or footnote
        if re.match(r"^\[?\d+\]?\s*$", sentence):
            return False
        # Skip if starts with URL
        if sentence.startswith(("http://", "https://")):
            return False
        return True

    def _is_quality_qa(self, q: str, a: str) -> bool:
        """Filtra pares Q&A de baja calidad."""
        # Question must be a real question (not a fragment)
        if not q.endswith(("?", "¿")):
            return False
        # Answer must be longer than the question stem
        if len(a) < 80:
            return False
        # Avoid questions that are just fragments of the answer
        if q.lower() in a.lower():
            return False
        return True

    def _reverse_to_question(self, sentence: str) -> Optional[str]:
        """Intenta convertir una oración en pregunta natural."""
        sentence = sentence.strip()
        if not sentence:
            return None

        # Pattern: "X is Y" / "The X is Y" → "¿Qué es X?"
        m = re.match(r"(?:The\s+)?(.+?)\s+is\s+(.+)", sentence, re.IGNORECASE)
        if m and len(m.group(2)) > 5:
            return f"¿Qué es {m.group(1).lower().rstrip('.')}?"

        # "X can be Y" → "¿Qué puede ser X?"
        m = re.match(r"(.+?)\s+can be\s+(.+)", sentence, re.IGNORECASE)
        if m:
            return f"¿Qué puede ser {m.group(1).lower().rstrip('.')}?"

        # "X is used for Y" → "¿Para qué se usa X?"
        m = re.match(r"(.+?)\s+is used for\s+(.+)", sentence, re.IGNORECASE)
        if m:
            return f"¿Para qué se usa {m.group(1).lower().rstrip('.')}?"

        # "X was Y" → "¿Qué fue X?"
        m = re.match(r"(.+?)\s+was\s+(.+)", sentence, re.IGNORECASE)
        if m:
            return f"¿Qué fue {m.group(1).lower().rstrip('.')}?"

        # "In X, Y happens" → "¿Qué es X?"
        m = re.match(r"In\s+(.+?),\s+(.+)", sentence, re.IGNORECASE)
        if m:
            return f"¿Qué es {m.group(1).lower().rstrip('.')}?"

        # "X has Y" → "¿Qué tiene X?"
        m = re.match(r"(.+?)\s+has\s+(.+)", sentence, re.IGNORECASE)
        if m:
            return f"¿Qué tiene {m.group(1).lower().rstrip('.')}?"

        # "X such as Y" / "X including Y" → "¿Qué incluye X?"
        m = re.match(r"(.+?)\s+(such as|including)\s+(.+)", sentence, re.IGNORECASE)
        if m:
            return f"¿Qué incluye {m.group(1).lower().rstrip('.')}?"

        # "X consists of Y" → "¿De qué consiste X?"
        m = re.match(r"(.+?)\s+consists of\s+(.+)", sentence, re.IGNORECASE)
        if m:
            return f"¿De qué consiste {m.group(1).lower().rstrip('.')}?"

        # Generic: "X" (starts with article) → extract noun phrase
        if sentence.startswith(("The ", "A ", "An ", "This ", "These ", "Those ")):
            m = re.match(r"(?:The|A|An|This|These|Those)\s+(.+?)\s+(?:is|was|are|can|has|consists|includes|such)\b", sentence, re.IGNORECASE)
            if m:
                return f"¿Qué es {m.group(1).lower().rstrip('.')}?"

        return None


class KnowledgeCollector:
    """Pipeline de colección de conocimiento: busca → extrae → genera → guarda."""

    def __init__(
        self,
        topics: List[str] = None,
        output_file: str = "training-data-web.jsonl",
        num_results: int = 5,
        samples_per_page: int = 5,
    ):
        self.topics = topics or ["AURA AI", "LLM fine-tuning", "Transformers"]
        self.output_file = Path(output_file)
        self.num_results = num_results
        self.samples_per_page = samples_per_page
        self.fetcher = WebFetcher()
        self.searcher = SearchEngine(self.fetcher)
        self.qa_gen = QAgenerator()
        self.collected: List[Dict] = []

    def collect_from_topics(self) -> List[Dict]:
        """Recolecta datos para cada topic configurado."""
        all_qa: List[Dict] = []

        for topic in self.topics:
            logger.info(f"\n{'='*50}")
            logger.info(f"Topic: {topic}")
            logger.info(f"{'='*50}")

            # Search
            urls = self.searcher.search(topic, self.num_results)
            logger.info(f"Found {len(urls)} URLs")

            # Extract + Generate QA
            for url in urls:
                html = self.fetcher.get(url)
                if html:
                    text = self.fetcher.extract_text(html)
                    qa_pairs = self.qa_gen.generate_from_text(text, url, self.samples_per_page)
                    all_qa.extend(qa_pairs)
                    logger.info(f"  {url}: {len(qa_pairs)} pares Q&A")
                time.sleep(random.uniform(1, 3))

            # Delay between topics
            time.sleep(random.uniform(2, 5))

        return all_qa

    def collect_from_query(self, query: str, num_results: int = 5, samples_per: int = 5) -> List[Dict]:
        """Recolecta datos para una query específica."""
        self.num_results = num_results
        self.samples_per_page = samples_per

        logger.info(f"\n{'='*50}")
        logger.info(f"Query: {query}")
        logger.info(f"{'='*50}")

        urls = self.searcher.search(query, num_results)
        logger.info(f"Found {len(urls)} URLs")

        all_qa: List[Dict] = []
        for url in urls:
            html = self.fetcher.get(url)
            if html:
                text = self.fetcher.extract_text(html)
                qa_pairs = self.qa_gen.generate_from_text(text, url, samples_per)
                all_qa.extend(qa_pairs)
                logger.info(f"  {url}: {len(qa_pairs)} pares Q&A")
            time.sleep(random.uniform(1, 3))

        return all_qa

    def collect_from_wiki(self, concept: str, count: int = 30) -> List[Dict]:
        """Recolecta datos de Wikipedia usando MediaWiki API (contenido completo)."""
        import httpx

        logger.info(f"Collecting from Wikipedia: {concept}")

        # 1. Buscar el artículo más relevante via search API
        search_url = (
            f"https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={quote_plus(concept)}&srlimit=3&format=json"
        )
        try:
            resp = httpx.get(search_url, timeout=15, headers={"User-Agent": SearchEngine.WIKI_UA})
            titles = [
                r["title"] for r in resp.json().get("query", {}).get("search", [])
            ]
        except Exception:
            titles = [concept]

        if not titles:
            titles = [concept]

        all_qa: List[Dict] = []
        for title in titles[:2]:
            logger.info(f"  Fetching: {title}")
            # 2. Fetch full article via action=parse (wikitext)
            parse_url = (
                f"https://en.wikipedia.org/w/api.php"
                f"?action=parse&page={quote_plus(title)}&format=json&prop=wikitext"
            )
            try:
                resp = httpx.get(parse_url, timeout=20, headers={"User-Agent": SearchEngine.WIKI_UA})
                if resp.status_code == 200:
                    data = resp.json()
                    wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
                    if wikitext:
                        # Extract text paragraphs from wikitext
                        paragraphs = self._extract_wiki_paragraphs(wikitext)
                        full_text = "\n".join(paragraphs)
                        wiki_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        qa = self.qa_gen.generate_from_text(full_text, wiki_url, count)
                        all_qa.extend(qa)
                        logger.info(f"    {len(qa)} pares Q&A de '{title}' ({len(full_text)} chars)")
            except Exception as e:
                logger.debug(f"Failed to fetch {title}: {e}")
            time.sleep(2)

        return all_qa

    def _extract_wiki_paragraphs(self, wikitext: str) -> List[str]:
        """Extrae párrafos de texto de wikitext, removiendo markup."""
        # Remove reference tags
        wikitext = re.sub(r"<ref[^>]*>.*?</ref>", "", wikitext, flags=re.DOTALL)
        # Remove templates {{...}}
        wikitext = re.sub(r"\{\{[^}]+\}\}", "", wikitext)
        # Remove wiki markup (bold/italic, links, etc.)
        wikitext = re.sub(r"'''|''|\[\[(?:[^\]|]+?\|)?([^\]|]+?)\]\]", r"\1", wikitext)
        # Remove remaining brackets
        wikitext = re.sub(r"<[^>]+>", " ", wikitext)
        # Split into lines/paragraphs
        lines = wikitext.split("\n")
        paragraphs = []
        for line in lines:
            line = line.strip()
            if len(line) > 50 and not line.startswith(("|", "!", "{", "}", "=", "<", "#")):
                paragraphs.append(line)
        return paragraphs

    def save(self, qa_pairs: List[Dict], append: bool = True) -> str:
        """Guarda pares Q&A en JSONL (merge con training-data.jsonl si append=True)."""
        if append and self.output_file.name == "training-data.jsonl":
            # Append to existing training data
            existing_count = 0
            if self.output_file.exists():
                with open(self.output_file) as f:
                    existing_count = sum(1 for _ in f)

            with open(self.output_file, "a", encoding="utf-8") as f:
                for pair in qa_pairs:
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")

            logger.info(f"Added {len(qa_pairs)} to {self.output_file} (total now {existing_count + len(qa_pairs)})")
            return str(self.output_file)

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            for pair in qa_pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(qa_pairs)} pairs to {self.output_file}")
        return str(self.output_file)


# ---------------------------------------------------------------------- #
#  CLI
# ---------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(description="AURA Knowledge Collector — web data collection")
    p.add_argument("--topics", nargs="+", default=["AURA AI", "LLM fine-tuning", "Transformers"], help="Topics to search")
    p.add_argument("--query", type=str, default=None, help="Single query to search")
    p.add_argument("--from-wiki", type=str, default=None, help="Collect from a Wikipedia concept")
    p.add_argument("--num-results", type=int, default=5, help="Results per search")
    p.add_argument("--samples-per-page", type=int, default=5, help="QA pairs per page")
    p.add_argument("--output", default="training-data-web.jsonl", help="Output file")
    p.add_argument("--append-to-main", action="store_true", help="Append to training-data.jsonl")

    args = p.parse_args()

    collector = KnowledgeCollector(
        topics=args.topics,
        output_file=args.output,
        num_results=args.num_results,
        samples_per_page=args.samples_per_page,
    )

    if args.query:
        qa = collector.collect_from_query(args.query, args.num_results, args.samples_per_page)
    elif args.from_wiki:
        qa = collector.collect_from_wiki(args.from_wiki, args.samples_per_page * args.num_results)
    else:
        qa = collector.collect_from_topics()

    if args.append_to_main:
        collector.output_file = Path("training-data.jsonl")

    output = collector.save(qa, append=True)
    print(f"\n[OK] Collected {len(qa)} Q&A pairs -> {output}")


if __name__ == "__main__":
    main()
