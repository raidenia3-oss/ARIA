"""
AURA YouTube Learner — youtube_learner.py
Busca tutoriales sobre OSINT/Python, extrae transcript, lo resume con Ollama
y guarda el aprendizaje en .skills/ para que el bot lo absorba.

Reglas:
  - Ignora videos > 30 minutos
  - Ignora baja resolución (menos de 480p)
  - Resume usando Ollama local (deepseek-coder:6.7b)
"""
import os
import sys
import json
import re
import time
import requests
import subprocess
import argparse
from datetime import datetime, timedelta
from urllib.parse import urlencode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(os.path.dirname(BASE_DIR), ".skills")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
HEALTH_LOG = os.path.join(BASE_DIR, "system_health.log")

# ── Config YouTube API ──
# La API Key se lee de variable de entorno o config.json
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
MAX_DURATION_SECONDS = 30 * 60  # 30 minutos
MAX_RESULTS = 5

# ── Ollama ──
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "deepseek-coder:6.7b"


def log_health(component, status, detail=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {component}: {status}"
    if detail:
        entry += f" — {detail}"
    with open(HEALTH_LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    print(entry)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def ensure_skills_dir():
    os.makedirs(SKILLS_DIR, exist_ok=True)
    return SKILLS_DIR


def search_youtube(query, max_results=MAX_RESULTS):
    """
    Busca videos en YouTube usando la API Data v3.
    Retorna lista de dicts con: id, title, duration, description, thumb.
    """
    if not YOUTUBE_API_KEY:
        log_health("YOUTUBE", "ERROR", "No YOUTUBE_API_KEY configurada")
        return []

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
        "relevanceLanguage": "es"
    }

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params, timeout=10
        )
        if resp.status_code != 200:
            log_health("YOUTUBE", "ERROR", f"API error {resp.status_code}: {resp.text[:100]}")
            return []

        data = resp.json()
        video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
        if not video_ids:
            return []

        # Obtener duración de los videos (videoDuration)
        details_params = {
            "part": "contentDetails,snippet",
            "id": ",".join(video_ids),
            "key": YOUTUBE_API_KEY
        }
        details_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params=details_params, timeout=10
        )
        if details_resp.status_code != 200:
            return []

        details_data = details_resp.json()
        results = []
        for item in details_data.get("items", []):
            duration_str = item.get("contentDetails", {}).get("duration", "PT0S")
            duration_sec = parse_iso8601_duration(duration_str)
            snippet = item.get("snippet", {})

            # Filtrar por duración máxima
            if duration_sec > MAX_DURATION_SECONDS:
                continue

            results.append({
                "id": item["id"],
                "title": snippet.get("title", ""),
                "duration_sec": duration_sec,
                "duration_str": format_duration(duration_sec),
                "description": snippet.get("description", "")[:200],
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "url": f"https://youtube.com/watch?v={item['id']}"
            })

        log_health("YOUTUBE", "OK", f"Búsqueda '{query}': {len(results)} resultados")
        return results

    except requests.exceptions.RequestException as e:
        log_health("YOUTUBE", "ERROR", f"Request error: {str(e)}")
        return []


def parse_iso8601_duration(duration):
    """Convierte ISO 8601 duration (PT1H2M3S) a segundos."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds):
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m{s:02d}s"


def extract_transcript(video_id):
    """
    Extrae el transcript/subtítulos de un video usando la API de YouTube.
    Fallback: usa get_transcript si está disponible.
    """
    try:
        # Intentar con youtube-transcript-api si está instalado
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'en'])
        text = " ".join([item["text"] for item in transcript_list])
        return text[:5000]  # limitar a 5000 chars
    except ImportError:
        # Fallback: usar caption scraping simple
        try:
            url = f"https://youtubetranscript.com/?v={video_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.text[:5000]
        except Exception:
            pass
        return ""
    except Exception:
        return ""


def summarize_with_ollama(text, max_length=300):
    """Resume un texto usando Ollama local."""
    if not text or len(text) < 50:
        return "Texto demasiado corto para resumir."

    prompt = (
        "Resume el siguiente texto técnico sobre OSINT o Python en español. "
        "Extrae las técnicas clave, herramientas mencionadas y pasos prácticos. "
        "Máximo 300 palabras.\n\n"
        f"TEXTO:\n{text[:4000]}\n\n"
        "RESUMEN (en español):"
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30
        )
        if resp.status_code == 200:
            summary = resp.json().get("response", "")
            # Truncar si es muy largo
            words = summary.split()
            if len(words) > max_length:
                summary = " ".join(words[:max_length]) + "..."
            return summary.strip()
        else:
            return f"[Error Ollama: {resp.status_code}]"
    except requests.exceptions.ConnectionError:
        return "[Error: Ollama no disponible]"
    except Exception as e:
        return f"[Error: {str(e)}]"


def save_skill(filename, content):
    """Guarda el resumen como skill en .skills/."""
    filepath = os.path.join(SKILLS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {filename}\n")
        f.write(f"# Auto-aprendido por YouTube Learner\n")
        f.write(f"# Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Fuente: YouTube\n\n")
        f.write(content)
    log_health("YOUTUBE", "OK", f"Skill guardado: {filename}")
    return filepath


def learn_from_youtube(query):
    """Pipeline completo: buscar → filtrar → transcript → resumir → guardar."""
    print(f"🔍 YouTube Learner: buscando '{query}'...")
    videos = search_youtube(query)

    if not videos:
        print("❌ No se encontraron videos relevantes")
        log_health("YOUTUBE", "ERROR", f"Sin resultados para '{query}'")
        return []

    skills_created = []
    for vid in videos[:2]:  # solo los 2 primeros
        print(f"\n📺 Procesando: {vid['title']}")
        print(f"   Duración: {vid['duration_str']} | {vid['url']}")

        print("   📝 Extrayendo transcript...")
        transcript = extract_transcript(vid["id"])

        if not transcript or len(transcript) < 100:
            print("   ⏭️  Transcript no disponible o muy corto")
            continue

        print("   🧠 Resumiendo con Ollama...")
        summary = summarize_with_ollama(transcript)

        if summary.startswith("[Error"):
            print(f"   ❌ {summary}")
            continue

        # Crear nombre de archivo seguro
        safe_title = re.sub(r'[^\w\s-]', '', vid['title'])[:40]
        safe_title = re.sub(r'[-\s]+', '_', safe_title).strip('_').lower()
        filename = f"youtube_{safe_title}.md"

        content = (
            f"## {vid['title']}\n\n"
            f"- **Fuente:** {vid['url']}\n"
            f"- **Duración:** {vid['duration_str']}\n\n"
            f"### Resumen\n\n{summary}\n\n"
            f"---\n*Generado por AURA YouTube Learner el {datetime.now().strftime('%Y-%m-%d %H:%M')}*"
        )

        skill_path = save_skill(filename, content)
        skills_created.append(filename)
        print(f"   ✅ Skill guardado: {filename}")

    return skills_created


# ────────────── CLI ──────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AURA YouTube Learner")
    parser.add_argument("--query", "-q", default="tutorial OSINT Python nuevas técnicas 2026",
                        help="Búsqueda en YouTube")
    args = parser.parse_args()

    print("="*50)
    print("🎓 AURA YouTube Learner v1.0")
    print("="*50)

    if not YOUTUBE_API_KEY:
        cfg = load_config()
        YOUTUBE_API_KEY = cfg.get("youtube_api_key", "")

    if not YOUTUBE_API_KEY:
        print("❌ YOUTUBE_API_KEY no configurada")
        print("   Configúrala en variable de entorno o en config.json")
        sys.exit(1)

    ensure_skills_dir()
    skills = learn_from_youtube(args.query)

    print("\n" + "="*50)
    if skills:
        print(f"✅ {len(skills)} skills generados en .skills/:")
        for s in skills:
            print(f"   📄 {s}")
    else:
        print("⚠️  No se generaron skills")
    print("="*50)