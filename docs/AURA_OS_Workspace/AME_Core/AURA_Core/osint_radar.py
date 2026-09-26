"""
AURA OSINT Radar — osint_radar.py v3
Módulo de inteligencia PREDICTIVA — Early Warning System.
Lee feeds RSS de fuentes fringe/deep web superficial, procesa con IA
y busca "señales tempranas" antes de que lleguen a medios masivos.

Novedades v3:
  - Fuentes raw/fringe (Liveuamap, CISA, GitHub exploits, r/geopolitics)
  - Prompt "Early Warning AI": ignora noticias comunes, busca anomalías
  - Reporte HTML clasificado: 🔴 ALERTAS ROJAS / 🟡 ANOMALÍAS / 🟢 SEÑALES DÉBILES
"""
import os
import json
import sys
import time
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

# ── Dependencias opcionales ──
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

# ── Fuentes RSS de ALERTA TEMPRANA (fringe/raw/geopolítica) ──
DEFAULT_FEEDS = [
    # Geopolítica y conflictos
    "https://www.reddit.com/r/geopolitics/.rss",
    "https://www.reddit.com/r/collapse/.rss",

    # Ciberseguridad — alertas y exploits
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.cisa.gov/cybersecurity-advisories/cybersecurity-bulletins.xml",
    "https://github.com/explore/trending.rss",

    # Mercados anómalos / fintech
    "https://www.reddit.com/r/wallstreetbets/.rss",
    "https://www.reddit.com/r/CryptoCurrency/.rss",

    # Señales tecnológicas tempranas (newest, no hot)
    "https://hnrss.org/newest?points=1&count=8",
]

BRIEFING_DIR = Path(__file__).parent.parent / "knowledge_base" / "briefings"
BRIEFING_DIR.mkdir(parents=True, exist_ok=True)


def fetch_raw_headlines(feeds: Optional[List[str]] = None, max_per_feed: int = 5) -> List[Dict]:
    """
    Obtiene titulares de múltiples fuentes RSS.
    Retorna lista de {"source": str, "title": str, "link": str, "published": str}
    """
    if not HAS_FEEDPARSER:
        return [{"error": "feedparser no instalado. pip install feedparser"}]

    if feeds is None:
        feeds = DEFAULT_FEEDS

    headlines = []
    seen_titles = set()
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                headlines.append({
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[OSINT Radar] Error en feed {url}: {e}")

    return headlines


def generar_briefing_tactico(headlines: List[Dict]) -> str:
    """
    Envía los titulares a la IA con prompt de Early Warning.
    Busca señales tempranas: rumores no confirmados, anomalías geopolíticas,
    movimientos inusuales de mercado, posibles ciberataques 0-day.
    Devuelve HTML directo con 3 secciones clasificadas por color.

    Si ai_router no está disponible, devuelve HTML plano con los titulares.
    """
    if not headlines:
        return "<p>No se obtuvieron titulares de las fuentes RSS.</p>"

    # Construir el texto plano con los titulares
    raw_items = []
    for h in headlines:
        raw_items.append(f"- [{h['source']}] {h['title']}")
    raw_text = "\n".join(raw_items)

    # Prompt de sistema — EARLY WARNING AI v2
    system_prompt = (
        "Eres una IA de Alerta Temprana (Early Warning). "
        "Analiza estos datos crudos. Busca anomalías, rumores no confirmados "
        "o señales débiles antes de que sean noticia mainstream. "
        "Clasifica en: 🔴 RIESGO INMINENTE, 🟡 ANOMALÍA, y 🟢 NORMAL. "
        "Responde en HTML estructurado EXACTAMENTE así:\n\n"
        "<div class='early-section early-red'>"
        "<span style='color:#ff3366;font-weight:700;font-size:0.8rem;'>🔴 RIESGO INMINENTE</span>"
        "<ul>\n<li>...</li>\n</ul>\n</div>\n\n"
        "<div class='early-section early-yellow'>"
        "<span style='color:#ffcc00;font-weight:700;font-size:0.8rem;'>🟡 ANOMALÍA</span>"
        "<ul>\n<li>...</li>\n</ul>\n</div>\n\n"
        "<div class='early-section early-green'>"
        "<span style='color:#00ff88;font-weight:700;font-size:0.8rem;'>🟢 NORMAL</span>"
        "<ul>\n<li>...</li>\n</ul>\n</div>\n\n"
        "Sé ultra-conciso: máximo 3 items por sección. "
        "Si una sección no tiene datos, pon <li><em>Ninguna señal detectada</em></li>. "
        "NO añadas markdown, NO añadas texto fuera del HTML. "
        "NO uses ```"
    )

    full_prompt = system_prompt + "\n\nDATOS CRUDOS:\n" + raw_text

    # Intentar usar ai_router para el análisis
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ai_router import AuraCognitiveRouter as _Router
        router = _Router()
        result = router.route(full_prompt)
        ai_response = result.get("response")
        if ai_response:
            # Limpiar posibles bloques markdown ```html ... ```
            cleaned = ai_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()
            # Asegurar que tenga la estructura de secciones esperada
            if "ALERTAS ROJAS" in cleaned or "ANOMALÍAS" in cleaned or "SEÑALES DÉBILES" in cleaned:
                return cleaned
            # Si la IA no siguió el formato exacto, intentar parsear igual
            return cleaned
    except Exception as e:
        print(f"[OSINT Radar] Error llamando ai_router: {e}")

    # Fallback: devolver titulares clasificados manualmente por fuente
    fallback_html = """
    <div class='early-section early-red'>
        <span style='color:#ff3366;font-weight:700;font-size:0.8rem;'>🔴 ALERTAS ROJAS (Inminente)</span>
        <ul>
    """
    # Fuentes de alta prioridad: CISA, Hacker News, exploits
    high_priority = ["Hacker News", "CISA", "GitHub"]
    for h in headlines[:4]:
        if any(p in h['source'] for p in high_priority):
            fallback_html += f'<li><strong>[{h["source"]}]</strong> {h["title"]}</li>\n'

    fallback_html += """
        </ul>
    </div>
    <div class='early-section early-yellow'>
        <span style='color:#ffcc00;font-weight:700;font-size:0.8rem;'>🟡 ANOMALÍAS (Probable)</span>
        <ul>
    """
    for h in headlines[4:8]:
        fallback_html += f'<li><strong>[{h["source"]}]</strong> {h["title"]}</li>\n'

    fallback_html += """
        </ul>
    </div>
    <div class='early-section early-green'>
        <span style='color:#00ff88;font-weight:700;font-size:0.8rem;'>🟢 SEÑALES DÉBILES (Posible)</span>
        <ul>
    """
    for h in headlines[8:12]:
        fallback_html += f'<li><strong>[{h["source"]}]</strong> {h["title"]}</li>\n'

    fallback_html += """
        </ul>
    </div>
    <p><em>🔍 Resumen IA no disponible — clasificación por fuente automática.</em></p>
    """
    return fallback_html


def summarize_headlines(headlines: List[Dict]) -> str:
    """
    Convierte los titulares en un texto para el resumen.
    Si ai_router está disponible, lo usa para generar un briefing táctico.
    """
    if not headlines:
        return "No se obtuvieron titulares."

    raw_text = "\n".join([f"- [{h['source']}] {h['title']}" for h in headlines])

    try:
        from ai_router import AuraCognitiveRouter as _Router
        router = _Router()
        prompt = (
            "Eres una IA de Alerta Temprana. "
            "Resume estos datos crudos identificando SOLO anomalías, "
            "movimientos inusuales o amenazas potenciales. "
            "Ignora noticias genéricas.\n\nDATOS:\n" + raw_text
        )
        result = router.route(prompt)
        if result.get("response"):
            return result["response"]
    except Exception:
        pass

    return raw_text


def fetch_morning_briefing(feeds: Optional[List[str]] = None) -> Dict:
    """
    Función principal: obtiene titulares de fuentes fringe → analiza con IA
    buscando señales tempranas → guarda en VOID.
    Retorna el briefing completo.
    """
    headlines = fetch_raw_headlines(feeds)
    summary = summarize_headlines(headlines)

    # Generar briefing táctico HTML con clasificación Early Warning
    tactical_html = generar_briefing_tactico(headlines)

    briefing = {
        "timestamp": datetime.now().isoformat(),
        "total_sources": len(feeds or DEFAULT_FEEDS),
        "total_headlines": len(headlines),
        "headlines": headlines[:10],
        "summary": summary,
        "tactical_html": tactical_html,
        "feed_type": "early_warning",
        "source_profiles": [
            "geopolitics: r/geopolitics + r/collapse",
            "cybersecurity: HackerNews + CISA + GitHub exploits",
            "markets: r/wallstreetbets + r/CryptoCurrency",
            "tech_early: HNRSS newest"
        ]
    }

    # Guardar en archivo JSON para el frontend
    today = datetime.now().strftime("%Y-%m-%d")
    briefing_file = BRIEFING_DIR / f"briefing_{today}.json"
    try:
        with open(briefing_file, "w", encoding="utf-8") as f:
            json.dump(briefing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[OSINT Radar] Error guardando briefing: {e}")

    # Guardar también en VOID para persistencia
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from void import save_to_void
        save_to_void(
            content=f"📡 EARLY WARNING BRIEFING {today}\n\n{summary}",
            tags=["briefing", "early_warning", "osint", "predictive"],
        )
    except Exception as e:
        print(f"[OSINT Radar] Error guardando en VOID: {e}")

    return briefing


def get_latest_briefing() -> Optional[Dict]:
    """Obtiene el briefing más reciente desde el archivo JSON."""
    files = sorted(BRIEFING_DIR.glob("briefing_*.json"), reverse=True)
    if not files:
        return None
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── Bloque de prueba ──
if __name__ == "__main__":
    print("🔍 AURA OSINT Radar v3 — Early Warning System")
    briefing = fetch_morning_briefing()
    print(f"   Titulares obtenidos: {briefing['total_headlines']}")
    print(f"   Resumen: {briefing['summary'][:200]}...")
    print(f"\n   Briefing táctico HTML (primeros 400 chars):")
    html_sample = briefing.get('tactical_html', 'N/A')
    print(f"   {html_sample[:400]}")
    print(f"\n   Feed type: {briefing.get('feed_type')}")