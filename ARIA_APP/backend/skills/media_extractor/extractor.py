from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import yt_dlp
import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "media_extracts")
os.makedirs(os.path.abspath(DATA_DIR), exist_ok=True)


def _sanitize_name(url: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", url)
    return safe[:80]


# ─── Extracción de video (yt-dlp, sin descargar el video) ──────────────────

def extract_video(url: str) -> Dict[str, Any]:
    """Extrae TODA la información disponible de un video sin descargarlo.

    Usa --dump-single-json --skip-download para obtener metadatos completos:
    título, descripción, duración, vistas, autor, fecha, capítulos,
    subtítulos disponibles, miniatura, tags, categoría, URL original, etc.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "forcejson": True,
        "dump_single_json": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
    }

    info: Dict[str, Any] = {}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        return {
            "status": "error",
            "skill": "media_extract_video",
            "url": url,
            "error": str(exc),
        }

    # Extraer capítulos si existen
    chapters: List[Dict[str, Any]] = []
    for ch in info.get("chapters") or []:
        chapters.append({
            "title": ch.get("title"),
            "start": ch.get("start_time"),
            "end": ch.get("end_time"),
            "start_str": _fmt_time(ch.get("start_time")),
            "end_str": _fmt_time(ch.get("end_time")),
        })

    # Subtítulos disponibles (solo listar cuáles hay, no descargar)
    subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    available_subs = {}
    for lang, entries in subs.items():
        available_subs[lang] = [e.get("url") for e in entries if e.get("url")]
    for lang, entries in auto_subs.items():
        if lang not in available_subs:
            available_subs[lang] = [e.get("url") for e in entries if e.get("url")]

    # Formatos de video/audio disponibles (calidades)
    formats = []
    for f in info.get("formats") or []:
        formats.append({
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "resolution": f.get("resolution"),
            "fps": f.get("fps"),
            "vcodec": f.get("vcodec"),
            "acodec": f.get("acodec"),
            "filesize": f.get("filesize") or f.get("filesize_approx"),
            "tbr": f.get("tbr"),  # total bitrate
        })

    result = {
        "status": "ok",
        "skill": "media_extract_video",
        "url": url,
        "id": info.get("id"),
        "title": info.get("title"),
        "description": info.get("description"),
        "description_clean": _clean_html(str(info.get("description") or "")),
        "uploader": info.get("uploader"),
        "uploader_id": info.get("uploader_id"),
        "channel": info.get("channel"),
        "channel_id": info.get("channel_id"),
        "duration": info.get("duration"),
        "duration_str": _fmt_time(info.get("duration")),
        "duration_string": info.get("duration_string"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "average_rating": info.get("average_rating"),
        "upload_date": info.get("upload_date"),
        "timestamp": info.get("timestamp"),
        "license": info.get("license"),
        "creator": info.get("creator"),
        "tags": info.get("tags"),
        "categories": info.get("categories"),
        "age_limit": info.get("age_limit"),
        "webpage_url": info.get("webpage_url"),
        "extractor": info.get("extractor"),
        "extractor_key": info.get("extractor_key"),
        "thumbnail": info.get("thumbnail"),
        "thumbnails": info.get("thumbnails"),
        "chapters": chapters,
        "chapter_count": len(chapters),
        "subtitles_available": available_subs,
        "subtitle_count": len(available_subs),
        "automatic_captions": {k: len(v) for k, v in auto_subs.items()},
        "formats": formats,
        "format_count": len(formats),
        "width": info.get("width"),
        "height": info.get("height"),
        "fps": info.get("fps"),
        "vcodec": info.get("vcodec"),
        "acodec": info.get("acodec"),
        "aspect_ratio": info.get("aspect_ratio"),
        "playable_in_embed": info.get("playable_in_embed"),
        "live_status": info.get("live_status"),
        "was_live": info.get("was_live"),
        "is_live": info.get("is_live"),
        "comment_count": info.get("comment_count"),
        "heatmap": info.get("heatmap"),
        "relevant_ids": info.get("relevant_ids"),
        "extracted_at": os.popen("date /t").read().strip() if os.name == "nt" else None,
    }
    return result


def extract_transcript(url: str, lang: Optional[str] = None,
                       cookies_from_browser: Optional[str] = None) -> Dict[str, Any]:
    """Intenta descargar los subtítulos/transcripción de un video.

    Soporta cookies_from_browser (ej. 'chrome', 'edge') para evitar el 429
    de YouTube en timedtext cuando el navegador tiene sesión iniciada.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang] if lang else ["all"],
        "subtitlesformat": "vtt",
    }
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = cookies_from_browser
    out_dir = os.path.abspath(DATA_DIR)
    ydl_opts["outtmpl"] = os.path.join(out_dir, "%(id)s.%(ext)s")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get("id", "unknown")
            ydl.process_info(info)
    except Exception as exc:
        msg = str(exc)
        hint = ""
        if "Sign in to confirm" in msg or "bot" in msg.lower():
            hint = "YouTube requiere cookies de autenticación. Usa cookies_from_browser='chrome' o 'edge', o exporta cookies a un archivo Netscape y pásalas con cookiefile."
        elif "Could not copy Chrome cookie database" in msg:
            hint = "Chrome/Edge está abierto y bloquea su base de datos de cookies. Cierra el navegador o exporta cookies manualmente."
        return {
            "status": "error",
            "skill": "media_extract_transcript",
            "url": url,
            "error": msg,
            "hint": hint,
        }

    # Buscar el archivo de subtítulos generado
    transcript_text = ""
    sub_file = None
    for ext in ("vtt", "srt", "json3"):
        candidate = os.path.join(out_dir, f"{video_id}.{lang or '*'}.{ext}")
        # yt-dlp usa %(id)s.lang.ext
        import glob as _glob
        matches = _glob.glob(os.path.join(out_dir, f"{video_id}.*.{ext}"))
        if matches:
            sub_file = matches[0]
            break

    if sub_file and os.path.exists(sub_file):
        try:
            with open(sub_file, "r", encoding="utf-8") as f:
                raw = f.read()
            transcript_text = _parse_subtitles(raw)
            os.remove(sub_file)
        except Exception as exc:
            return {
                "status": "error",
                "skill": "media_extract_transcript",
                "url": url,
                "error": f"no se pudo leer subtítulos: {exc}",
                "video_id": video_id,
            }

    return {
        "status": "ok" if transcript_text else "warning",
        "skill": "media_extract_transcript",
        "url": url,
        "video_id": video_id,
        "language": lang,
        "transcript": transcript_text,
        "transcript_length": len(transcript_text),
        "message": "Transcripción extraída completamente" if transcript_text else "No se encontraron subtítulos para este video",
    }


def _fmt_time(seconds) -> str:
    if seconds is None:
        return "0:00"
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return "0:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_subtitles(raw: str) -> str:
    """Convierte VTT/SRT a texto plano limpio."""
    lines = raw.splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if re.match(r"^\d+:\d{2}:\d{2}", line):  # timestamp VTT
            continue
        if re.match(r"^\d+$", line):  # número SRT
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        out.append(line)
    return " ".join(out)


# ─── Extracción de sitio web ───────────────────────────────────────────────

def extract_web(url: str) -> Dict[str, Any]:
    """Extrae TODA la información de un sitio web: título, meta, contenido,
    encabezados, enlaces, imágenes, texto completo, fecha, autor si existe."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        return {
            "status": "error",
            "skill": "media_extract_web",
            "url": url,
            "error": str(exc),
        }

    soup = BeautifulSoup(html, "lxml")

    # Título
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)

    # Meta tags
    meta = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or tag.get("property") or tag.get("itemprop")
        content = tag.get("content")
        if name and content:
            meta[name.strip()] = content.strip()

    # Encabezados
    headings = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            txt = h.get_text(" ", strip=True)
            if txt:
                headings.append({"level": level, "text": txt})

    # Enlaces
    links = []
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True)
        href = a["href"]
        links.append({"text": txt[:120], "href": href})

    # Imágenes
    images = []
    for img in soup.find_all("img", src=True):
        images.append({
            "src": img["src"],
            "alt": img.get("alt", ""),
            "title": img.get("title", ""),
        })

    # Contenido principal (intentar encontrar el artículo/contenido principal)
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|post|entry|main", re.I))
    if main:
        main_text = main.get_text(" ", strip=True)
    else:
        # quitar nav, header, footer, aside, script, style
        for bad in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
            bad.decompose()
        main_text = soup.get_text(" ", strip=True)

    main_text = re.sub(r"\s+", " ", main_text).strip()

    # Fecha de publicación (intento común)
    published = None
    for prop in ["article:published_time", "datePublished", "pubdate"]:
        if prop in meta:
            published = meta[prop]
            break
    if not published:
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            published = time_tag["datetime"]

    # Autor
    author = None
    for prop in ["article:author", "author"]:
        if prop in meta:
            author = meta[prop]
            break

    result = {
        "status": "ok",
        "skill": "media_extract_web",
        "url": url,
        "title": title,
        "meta": meta,
        "description": meta.get("description") or meta.get("og:description"),
        "author": author,
        "published": published,
        "site_name": meta.get("og:site_name") or meta.get("application-name"),
        "headings": headings,
        "heading_count": len(headings),
        "links": links,
        "link_count": len(links),
        "images": images,
        "image_count": len(images),
        "content": main_text,
        "content_length": len(main_text),
        "content_preview": main_text[:2000],
        "language": (soup.html.get("lang") if soup.html else None),
        "charset": None,
        "extracted_at": os.popen("date /t").read().strip() if os.name == "nt" else None,
    }
    # charset
    m = re.search(r'charset=["\']?([\w-]+)', html, re.I)
    if m:
        result["charset"] = m.group(1)
    return result


def save_extract(skill: str, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Guarda el extracto en disco para consultarlo después (RAG/memoria)."""
    name = _sanitize_name(url)
    path = os.path.join(os.path.abspath(DATA_DIR), f"{skill}_{name}.json")
    payload = {
        "skill": skill,
        "url": url,
        "data": data,
        "saved_at": data.get("extracted_at"),
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "saved": path}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ─── Dispatcher ────────────────────────────────────────────────────────────

def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")

    if action == "extract_video":
        url = params.get("url", "")
        if not url:
            return {"error": "url requerido"}
        result = extract_video(url)
        if result.get("status") == "ok":
            save_extract("video", url, result)
        return result

    if action == "extract_web":
        url = params.get("url", "")
        if not url:
            return {"error": "url requerido"}
        result = extract_web(url)
        if result.get("status") == "ok":
            save_extract("web", url, result)
        return result

    if action == "extract_transcript":
        url = params.get("url", "")
        if not url:
            return {"error": "url requerido"}
        lang = params.get("lang")
        cookies = params.get("cookies_from_browser")
        result = extract_transcript(url, lang, cookies)
        if result.get("status") == "ok":
            save_extract("transcript", url, result)
        return result

    if action == "extract_all":
        url = params.get("url", "")
        if not url:
            return {"error": "url requerido"}
        results = {"url": url}
        # Determinar si es video o web por la URL
        video_domains = ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "facebook.com/watch", "tiktok.com", "instagram.com/reel")
        if any(d in url.lower() for d in video_domains):
            results["video"] = extract_video(url)
            if results["video"].get("status") == "ok":
                results["transcript"] = extract_transcript(url, params.get("lang"))
        else:
            results["web"] = extract_web(url)
        return {"status": "ok", "skill": "media_extract_all", "results": results}

    return {"error": f"acción desconocida: {action}"}
