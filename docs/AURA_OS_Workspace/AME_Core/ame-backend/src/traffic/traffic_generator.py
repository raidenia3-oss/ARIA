#!/usr/bin/env python3
"""
traffic_generator.py — Motor de generación de tráfico autónomo.
Consume feeds RSS de tendencias IA, reescribe títulos con estilo atractivo
(clickbait ético) y genera micro-publicaciones estructuradas con UTM tags.
"""

from __future__ import annotations

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
import random
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SOURCE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SOURCE_DIR / "output"

RSS_FEEDS = [
    "https://hnrss.org/frontpage?q=AI&count=5",
    "https://news.google.com/rss/search?q=artificial+intelligence+trending&hl=en-US&gl=US&ceid=US:en",
    "https://www.reddit.com/r/artificial/.rss",
    "https://www.reddit.com/r/MachineLearning/.rss",
]

POWER_WORDS = [
    "Increíble", "Revolucionario", "Descubren", "Nuevo", "Gratis",
    "Ultra-rápido", "Open Source", "Sin límites", "Épico", "Alucinante",
    "Expertos", "El futuro de la IA", "Gratuito", "Impresionante",
    "Cambia las reglas", "Innovador", "Acceso libre", "Ahora disponible",
]

UTM_SOURCE = "aura_traffic"
UTM_MEDIUM = "rss"
UTM_CAMPAIGN = "ia_trending"
LANDING_BASE = "https://aura-ia.vercel.app/recurso"

def _fetch_rss_feed(url: str, timeout: int = 10) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AURA-TrafficBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _parse_rss_entries(xml_data: str, max_entries: int = 4) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    try:
        root = ET.fromstring(xml_data)
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is not None and title_el.text:
                entries.append({
                    "title": title_el.text.strip(),
                    "url": link_el.text.strip() if link_el is not None and link_el.text else "https://example.com/ai",
                })
                if len(entries) >= max_entries:
                    break
        if not entries:
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title_el = entry.find("{http://www.w3.org/2005/Atom}title")
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                href = link_el.get("href") if link_el is not None else None
                if title_el is not None and title_el.text:
                    entries.append({
                        "title": title_el.text.strip(),
                        "url": href or "https://example.com/ai",
                    })
                    if len(entries) >= max_entries:
                        break
        if not entries:
            for entry in root.iter("entry"):
                title_el = entry.find("title")
                link_el = entry.find("link")
                href = link_el.get("href") if link_el is not None else None
                if title_el is not None and title_el.text:
                    entries.append({
                        "title": title_el.text.strip(),
                        "url": href or "https://example.com/ai",
                    })
                    if len(entries) >= max_entries:
                        break
    except ET.ParseError:
        pass
    return entries


def _rewrite_title(original: str) -> str:
    cleaned = re.sub(r"\s*[-–|]\s*(.*AI|.*Artificial.*Intelligence|.*Machine Learning).*", "", original, flags=re.IGNORECASE).strip()
    if not cleaned:
        cleaned = original
    prefix = random.choice(POWER_WORDS)
    suffix = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned
    patterns = [
        f"{prefix}: {suffix}",
        f"{suffix} — ¡{prefix}!",
        f"🔥 {prefix}: {suffix}",
        f"🚀 {suffix} [{prefix}]",
        f"{prefix} — {suffix}",
    ]
    return random.choice(patterns)


def _build_utm_url(base_url: str, title_slug: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title_slug.lower()).strip("-")[:30]
    utm = (
        f"utm_source={UTM_SOURCE}&utm_medium={UTM_MEDIUM}"
        f"&utm_campaign={UTM_CAMPAIGN}&utm_content={slug}"
    )
    return f"{LANDING_BASE}?{utm}"


def fetch_trends(max_items: int = 5) -> List[Dict[str, Any]]:
    seen_urls: set = set()
    all_entries: List[Dict[str, str]] = []
    feed_order = RSS_FEEDS.copy()
    random.shuffle(feed_order)
    for url in feed_order:
        xml_data = _fetch_rss_feed(url)
        if xml_data:
            entries = _parse_rss_entries(xml_data, max_entries=max_items)
            for e in entries:
                if e["url"] not in seen_urls:
                    seen_urls.add(e["url"])
                    all_entries.append(e)
        if len(all_entries) >= max_items:
            break
    if not all_entries:
        all_entries = _mock_entries(max_items)
    trends: List[Dict[str, Any]] = []
    for entry in all_entries[:max_items]:
        new_title = _rewrite_title(entry["title"])
        slug = re.sub(r"[^a-z0-9]+", "-", new_title.lower()).strip("-")[:30]
        trends.append({
            "id": f"trend-{int(time.time())}-{len(trends)}",
            "original_title": entry["title"],
            "title": new_title,
            "source_url": entry["url"],
            "landing_url": _build_utm_url(entry["url"], slug),
            "category": random.choice(["herramienta", "modelo", "tutorial", "noticia", "open-source"]),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
    return trends


def _mock_entries(count: int) -> List[Dict[str, str]]:
    mock = [
        "Claude 4 supera a GPT-4o en razonamiento lógico",
        "Mistral lanza modelo open-source de 70B parámetros",
        "Google Gemini ahora permite ejecución local de código",
        "Microsoft presenta Copilot para VS Code con auto-completado predictivo",
        "Stability AI libera Stable Diffusion 4 con control de estilo mejorado",
    ]
    return [{"title": t, "url": f"https://example.com/mock-{i}"} for i, t in enumerate(mock[:count])]


def generate_batch(count: int = 5) -> List[Dict[str, Any]]:
    trends = fetch_trends(max_items=count)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    filepath = OUTPUT_DIR / f"trends_{timestamp}.json"
    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_count": len(trends),
            "campaign": UTM_CAMPAIGN,
        },
        "trends": trends,
    }
    filepath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return trends


if __name__ == "__main__":
    print("=== Traffic Generator ===")
    batch = generate_batch()
    print(f"Generados {len(batch)} micro-publicaciones:")
    for item in batch:
        print(f"  [{item['category']}] {item['title']}")
        print(f"    -> {item['landing_url']}")
    print(f"Archivo guardado en: {OUTPUT_DIR}")
