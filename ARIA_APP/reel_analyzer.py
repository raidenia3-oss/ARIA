# -*- coding: utf-8 -*-
"""ARIA - Analizador de reels: de un link saca caption + transcripcion + frames.

Sin subprocess, sin servidores (Regla v2): yt-dlp (API Python) descarga, cv2 saca
frames, faster-whisper transcribe el audio en tu CPU (local). Instagram pide login:
se leen las COOKIES del navegador donde ya tienes sesion (no se guarda credencial).

Requiere: yt-dlp, opencv (cv2), faster-whisper. Salida en data/reels/<id>/.
"""
import os
import glob
import time

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reels")


def disponible():
    try:
        import yt_dlp  # noqa
        import cv2  # noqa
        return True
    except Exception:
        return False


def _sacar_frames(mp4, carpeta, n=6):
    import cv2
    frames = []
    cap = cv2.VideoCapture(mp4)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total <= 0:
        cap.release()
        return frames
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * i / max(1, n)))
        ok, fr = cap.read()
        if ok and fr is not None:
            fp = os.path.join(carpeta, "frame_%02d.jpg" % i)
            cv2.imwrite(fp, fr)
            frames.append(fp)
    cap.release()
    return frames


def _transcribir(mp4, modelo="base"):
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(modelo, device="cpu", compute_type="int8")
        segs, info = m.transcribe(mp4, vad_filter=True)
        texto = " ".join(s.text.strip() for s in segs).strip()
        return texto, getattr(info, "language", "?")
    except Exception as exc:
        return "(transcripcion no disponible: %s - instala faster-whisper)" % exc, "?"


# --- integracion con la boveda cifrada (login privado: solo ARIA lo lee) ---
_VAULT_KEY = "INSTAGRAM_COOKIES"   # texto del cookies.txt, cifrado en la boveda


def importar_cookies(vault, ruta_cookies):
    """Lee un cookies.txt (exportado del navegador una vez) y lo guarda CIFRADO en
    la boveda. Despues puedes borrar el archivo: el login vive solo en la boveda."""
    try:
        with open(ruta_cookies, "r", encoding="utf-8", errors="replace") as f:
            contenido = f.read()
    except Exception as exc:
        return {"error": "no pude leer %s: %s" % (ruta_cookies, exc)}
    if "# Netscape" not in contenido and "\t" not in contenido:
        return {"error": "no parece un cookies.txt valido (formato Netscape)"}
    r = vault.set(_VAULT_KEY, contenido)
    if not r.get("ok"):
        return r
    return {"ok": True, "guardado": "login de Instagram cifrado en la boveda"}


def _cookies_desde_vault(vault, carpeta):
    """Si la boveda tiene el login, lo descifra a un cookies.txt TEMPORAL (0600) que
    se borra tras usarlo. Devuelve la ruta temporal o None."""
    try:
        if vault is None or not vault.abierta():
            return None
        txt = vault.get(_VAULT_KEY)
        if not txt:
            return None
        tmp = os.path.join(carpeta, ".cookies_vault.txt")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(txt)
        try:
            os.chmod(tmp, 0o600)   # solo el usuario (best-effort; Windows lo ignora)
        except Exception:
            pass
        return tmp
    except Exception:
        return None


def _bloqueo_db(exc):
    s = str(exc).lower()
    return ("database is locked" in s or "permission denied" in s or
            "could not copy" in s or "locked" in s)


def _fuentes_cookies(navegador):
    if navegador:
        return [(navegador,)]
    fuentes = []
    for b in ("firefox", "edge", "chrome"):
        fuentes.append(("navegador", b))
    cookie_path = os.environ.get("ARIA_REEL_COOKIES")
    if not cookie_path:
        cookie_path = os.path.join(_DIR, "cookies.txt")
    if os.path.isfile(cookie_path):
        fuentes.append(("archivo", cookie_path))
    return fuentes


aria_vault = None


def analizar(url, n_frames=6, modelo="base", navegador=None, vault=None):
    """Descarga el reel y devuelve caption + transcripcion + frames (rutas).

    Si 'vault' (boveda abierta) tiene el login de Instagram, se usa PRIMERO: se
    descifra a un cookies.txt temporal que se borra al terminar. Asi el login vive
    solo cifrado (privado: solo ARIA lo lee)."""
    if vault is None:
        vault = globals().get("aria_vault")
    if not disponible():
        return {"error": "faltan yt-dlp / opencv (pip install yt-dlp opencv-contrib-python)"}
    import yt_dlp
    carpeta = os.path.join(_DIR, str(int(time.time())))
    os.makedirs(carpeta, exist_ok=True)

    # login desde la boveda (prioridad maxima) -> cookies.txt temporal
    cookies_tmp = _cookies_desde_vault(vault, carpeta)
    fuentes = list(_fuentes_cookies(navegador))
    if cookies_tmp:
        fuentes.insert(0, ("archivo", cookies_tmp))

    ultimo_error = None
    fuente = None
    info = None
    for tipo, valor in fuentes:
        opts = {
            "outtmpl": os.path.join(carpeta, "video.%(ext)s"),
            "format": "mp4/bestvideo+bestaudio/best",
            "writeinfojson": True,
            "quiet": True, "noprogress": True, "noplaylist": True,
        }
        if tipo == "navegador":
            opts["cookiesfrombrowser"] = (valor,)
            fuente = "navegador:%s" % valor
        else:
            opts["cookiefile"] = valor
            fuente = "boveda" if (cookies_tmp and valor == cookies_tmp) else "archivo:%s" % valor
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info = y.extract_info(url, download=True)
            break
        except Exception as exc:
            ultimo_error = exc
            continue

    # borra el cookies.txt temporal descifrado (el login queda solo en la boveda)
    if cookies_tmp:
        try:
            os.remove(cookies_tmp)
        except Exception:
            pass

    if info is None:
        return {"error": "descarga fallo: %s" % ultimo_error,
                "pista": ("loguéate en Firefox o exporta cookies.txt; "
                          "fuentes probadas: firefox, edge, chrome, cookies.txt"),
                "fuente": None}

    vids = [f for f in glob.glob(os.path.join(carpeta, "video.*"))
            if f.rsplit(".", 1)[-1].lower() in ("mp4", "mkv", "webm", "mov")]
    if not vids:
        return {"error": "no se descargo el video"}
    mp4 = vids[0]
    caption = (info.get("description") or info.get("title") or "").strip()
    autor = info.get("uploader") or info.get("channel") or ""
    frames = _sacar_frames(mp4, carpeta, n_frames)
    transcripcion, idioma = _transcribir(mp4, modelo)
    resumen = ("Reel de %s | caption: %s | transcripcion (%s): %s"
               % (autor or "?", (caption[:120] or "(sin caption)"), idioma,
                  (transcripcion[:200] or "(sin audio)")))
    return {"ok": True, "autor": autor, "caption": caption, "transcripcion": transcripcion,
            "idioma": idioma, "frames": frames, "video": mp4, "carpeta": carpeta,
            "resumen": resumen, "fuente": fuente}
