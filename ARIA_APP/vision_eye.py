# -*- coding: utf-8 -*-
"""Ojos de Dios - Vision local en vivo para ARIA. Sin servidores, sin puertos.

Base (todo local, en proceso):
  - Captura de la camara propia (webcam index, o una URL de stream que TU indiques).
  - Ver el ambiente: brillo, movimiento y cuantas caras hay.
  - Reconocer a Raiden: enrolas tu cara una vez (LBPH) y luego ARIA sabe si eres tu,
    si hay alguien DESCONOCIDO, o si no hay nadie. (No identifica a extraños: solo
    distingue 'tu' de 'desconocido' — util para seguridad/anti-secuestro.)
  - Vigilar: ante movimiento o rostro desconocido guarda una captura con fecha.

Requiere opencv-contrib-python (cv2 + cv2.face). ARIA arranca sin esto; la vision
solo se activa si esta instalado.
"""
import os
import time
import json

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vision")


def _ensure_dir():
    try:
        os.makedirs(_DIR, exist_ok=True)
    except Exception:
        pass
    return _DIR


def disponible():
    try:
        import cv2  # noqa
        return True
    except Exception:
        return False


def _cascade():
    import cv2
    ruta = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    return cv2.CascadeClassifier(ruta)


def _abrir(source=0):
    import cv2
    cap = cv2.VideoCapture(source)
    return cap if cap.isOpened() else None


def capturar(source=0):
    """Devuelve un frame (numpy BGR) o None."""
    import cv2  # noqa
    cap = _abrir(source)
    if cap is None:
        return None
    try:
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def _caras(frame):
    import cv2
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    casc = _cascade()
    return casc.detectMultiScale(gris, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60)), gris


def _movimiento(f1, f2, umbral=25):
    """Ratio de pixeles que cambiaron entre dos frames (0..1) y cajas de movimiento."""
    import cv2
    import numpy as np
    g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
    g1 = cv2.GaussianBlur(g1, (21, 21), 0)
    g2 = cv2.GaussianBlur(g2, (21, 21), 0)
    dif = cv2.absdiff(g1, g2)
    _, th = cv2.threshold(dif, umbral, 255, cv2.THRESH_BINARY)
    th = cv2.dilate(th, None, iterations=2)
    ratio = float(np.count_nonzero(th)) / th.size
    cont, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cajas = [cv2.boundingRect(c) for c in cont if cv2.contourArea(c) > 800]
    return ratio, cajas


def ver_ambiente(source=0, segundos=3):
    """Mira unos segundos y resume: brillo, movimiento y caras. Guarda una captura."""
    import cv2
    import numpy as np
    if not disponible():
        return {"error": "opencv no instalado (pip install opencv-contrib-python)"}
    cap = _abrir(source)
    if cap is None:
        return {"error": "no pude abrir la camara/stream: %r" % source}
    prev = None
    mov_max = 0.0
    caras_max = 0
    ultimo = None
    t0 = time.time()
    try:
        while time.time() - t0 < max(1, segundos):
            ok, frame = cap.read()
            if not ok:
                break
            ultimo = frame
            if prev is not None:
                r, _ = _movimiento(prev, frame)
                mov_max = max(mov_max, r)
            caras, _g = _caras(frame)
            caras_max = max(caras_max, len(caras))
            prev = frame
            time.sleep(0.05)
    finally:
        cap.release()
    if ultimo is None:
        return {"error": "sin frames"}
    brillo = float(np.mean(cv2.cvtColor(ultimo, cv2.COLOR_BGR2GRAY))) / 255.0
    snap = os.path.join(_ensure_dir(), "ambiente_%d.jpg" % int(time.time()))
    try:
        cv2.imwrite(snap, ultimo)
    except Exception:
        snap = None
    estado = "movimiento" if mov_max > 0.02 else "quieto"
    resumen = "Ambiente %s. Brillo %d%%. %d cara(s) detectada(s)." % (estado, int(brillo * 100), caras_max)
    return {"movimiento": round(mov_max, 4), "caras": caras_max, "brillo": round(brillo, 3),
            "estado": estado, "captura": snap, "resumen": resumen}


# --------------------------------------------------- Reconocer al dueño (LBPH)
def _modelo_path():
    return os.path.join(_ensure_dir(), "rostros.yml"), os.path.join(_ensure_dir(), "rostros.json")


def enrolar(nombre="raiden", source=0, muestras=25):
    """Captura varias muestras de TU cara y entrena el reconocedor local."""
    import cv2
    import numpy as np
    if not disponible():
        return {"error": "opencv no instalado"}
    cap = _abrir(source)
    if cap is None:
        return {"error": "no pude abrir la camara"}
    caras, etiquetas = [], []
    casc = _cascade()
    t0 = time.time()
    try:
        while len(caras) < muestras and time.time() - t0 < 30:
            ok, frame = cap.read()
            if not ok:
                break
            gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for (x, y, w, h) in casc.detectMultiScale(gris, 1.2, 5, minSize=(60, 60)):
                caras.append(cv2.resize(gris[y:y + h, x:x + w], (160, 160)))
                etiquetas.append(0)
            time.sleep(0.05)
    finally:
        cap.release()
    if len(caras) < 5:
        return {"error": "no capte suficientes muestras de tu cara (%d)" % len(caras)}
    rec = cv2.face.LBPHFaceRecognizer_create()
    rec.train(caras, np.array(etiquetas))
    ymlp, jsonp = _modelo_path()
    rec.write(ymlp)
    json.dump({"0": nombre}, open(jsonp, "w", encoding="utf-8"))
    return {"ok": True, "muestras": len(caras), "resumen": "Listo, Raiden: aprendi tu cara (%d muestras)." % len(caras)}


def reconocer(source=0, umbral=70.0):
    """Devuelve si el rostro es el dueño, 'desconocido', o 'sin rostro'."""
    import cv2
    if not disponible():
        return {"error": "opencv no instalado"}
    ymlp, jsonp = _modelo_path()
    if not os.path.isfile(ymlp):
        return {"error": "aun no enrolaste tu cara (usa enrolar)"}
    frame = capturar(source)
    if frame is None:
        return {"error": "no pude capturar"}
    caras, gris = _caras(frame)
    if len(caras) == 0:
        return {"resultado": "sin rostro", "resumen": "No veo a nadie ahora mismo."}
    rec = cv2.face.LBPHFaceRecognizer_create()
    rec.read(ymlp)
    nombres = json.load(open(jsonp, encoding="utf-8"))
    out = []
    for (x, y, w, h) in caras:
        roi = cv2.resize(gris[y:y + h, x:x + w], (160, 160))
        etiqueta, dist = rec.predict(roi)
        if dist <= umbral:
            out.append(nombres.get(str(etiqueta), "dueno"))
        else:
            out.append("desconocido")
    dueno = any(o not in ("desconocido",) for o in out)
    hay_desc = any(o == "desconocido" for o in out)
    if dueno and not hay_desc:
        res = "Eres tu, Raiden."
    elif dueno and hay_desc:
        res = "Estas tu y alguien mas (desconocido)."
    else:
        res = "Hay %d rostro(s) DESCONOCIDO(s)." % out.count("desconocido")
    return {"resultado": out, "dueno_presente": dueno, "desconocido": hay_desc, "resumen": res}


def vigilar(source=0, ciclos=20, intervalo=0.5):
    """Monitoreo: ante movimiento o rostro desconocido guarda captura con fecha."""
    import cv2
    if not disponible():
        return {"error": "opencv no instalado"}
    cap = _abrir(source)
    if cap is None:
        return {"error": "no pude abrir la camara"}
    eventos = []
    prev = None
    try:
        for _ in range(max(1, ciclos)):
            ok, frame = cap.read()
            if not ok:
                break
            disparo = None
            if prev is not None:
                r, cajas = _movimiento(prev, frame)
                if r > 0.03:
                    disparo = "movimiento (%.1f%%)" % (r * 100)
            caras, _g = _caras(frame)
            if len(caras) > 0:
                disparo = (disparo + " + rostro") if disparo else "rostro"
            if disparo:
                snap = os.path.join(_ensure_dir(), "alerta_%d.jpg" % int(time.time() * 1000))
                try:
                    cv2.imwrite(snap, frame)
                except Exception:
                    snap = None
                eventos.append({"t": time.time(), "motivo": disparo, "captura": snap})
            prev = frame
            time.sleep(intervalo)
    finally:
        cap.release()
    return {"eventos": eventos, "resumen": "Vigilancia: %d evento(s) capturado(s)." % len(eventos)}
def ver_url(url):
    """Descarga un video (Short/Reel) y extrae frames clave. Requiere yt-dlp."""
    try:
        import yt_dlp
    except Exception:
        return {"status": "error", "error": "DEPENDENCIA PROPUESTA: yt-dlp | para descargar Shorts/Reels | alternativa: pegar capturas manuales"}
    try:
        import cv2
    except Exception:
        return {"status": "error", "error": "opencv no instalado"}
    _ensure_dir()
    out = os.path.join(_DIR, "video_tmp.mp4")
    try:
        ydl_opts = {"outtmpl": out, "format": "mp4", "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    cap = cv2.VideoCapture(out)
    frames = []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, total // 5)
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            n = len(_caras(frame))
            frames.append({"idx": i, "caras": n, "brillo": float(gray.mean())})
        i += 1
    cap.release()
    try:
        os.remove(out)
    except Exception:
        pass
    return {"status": "ok", "url": url, "total_frames": total, "muestras": frames}
import re, json, urllib.request


def _yt_id(url):
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def ver_url_preview(url):
    """Ver un video (Short/Reel) SIN descargar: metadata + thumbnail publico."""
    out = {"url": url, "descarga": False}
    vid = _yt_id(url)
    if vid:
        out["plataforma"] = "youtube"
        out["video_id"] = vid
        out["thumbnail"] = "https://img.youtube.com/vi/%s/maxresdefault.jpg" % vid
        try:
            oembed = "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json" % vid
            with urllib.request.urlopen(oembed, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            out["titulo"] = data.get("title")
            out["autor"] = data.get("author_name")
            out["thumbnail"] = data.get("thumbnail_url") or out["thumbnail"]
        except Exception as exc:
            out["oembed_error"] = str(exc)
        return out
    # Instagram / otros: intentar oEmbed generico
    try:
        oembed = "https://www.instagram.com/oembed/?url=" + urllib.request.quote(url, safe="")
        with urllib.request.urlopen(oembed, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        out["plataforma"] = "instagram"
        out["titulo"] = data.get("title")
        out["autor"] = data.get("author_name")
        out["thumbnail"] = data.get("thumbnail_url")
        return out
    except Exception as exc:
        out["status"] = "error"
        out["error"] = "no se pudo obtener preview: %s" % exc
        return out

def ver_imagen_url(url):
    """Obtiene una imagen (thumbnail/captura) sin descargar video. Solo stdlib + PIL opcional."""
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = r.read()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    _ensure_dir()
    path = os.path.join(_DIR, "img_tmp.jpg")
    try:
        with open(path, "wb") as f:
            f.write(data)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    info = {"status": "ok", "url": url, "bytes": len(data), "guardado": path}
    try:
        from PIL import Image
        img = Image.open(path)
        info["size"] = img.size
        info["mode"] = img.mode
        # color dominante simple
        small = img.resize((32, 32)).convert("RGB")
        pixels = list(small.getdata())
        from collections import Counter
        dom = Counter(pixels).most_common(1)[0][0]
        info["color_dominante"] = dom
    except Exception:
        pass
    return info