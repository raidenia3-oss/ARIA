# -*- coding: utf-8 -*-
"""Pulso del Planeta (antes 'Ojos de Dios'): agregador de datos publicos en vivo
para ARIA. Sin servidores, sin puertos: solo salidas GET con la stdlib (urllib).

Fuentes gratuitas y SIN clave:
  - Sismos        : USGS  (earthquake.usgs.gov, GeoJSON)
  - Clima espacial: NOAA SWPC (indice Kp planetario)
  - ISS           : wheretheiss.at (posicion en vivo)

Automatizacion: cache en memoria con TTL por fuente (no martillea las APIs).
Compatibilidad: snapshot(lat_min, lon_min, lat_max, lon_max) sigue existiendo.
"""
import json
import time
import urllib.request
import urllib.error

_UA = "ARIA-PulsoDelPlaneta/1.0 (+local; stdlib-urllib)"
_CACHE = {}  # clave -> (expira_ts, valor)


def _fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_json(url, timeout=15):
    raw = _fetch(url, timeout)
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception as exc:
        return {"error": str(exc)}


def _cached(clave, ttl, fn):
    ahora = time.time()
    hit = _CACHE.get(clave)
    if hit and hit[0] > ahora:
        return hit[1]
    val = fn()
    # solo cachea exitos (no errores) para reintentar pronto si fallo
    if not (isinstance(val, dict) and val.get("error")):
        _CACHE[clave] = (ahora + ttl, val)
    return val


def _en_bbox(lat, lon, bbox):
    if not bbox:
        return True
    la0, lo0, la1, lo1 = bbox
    return (min(la0, la1) <= lat <= max(la0, la1)) and (min(lo0, lo1) <= lon <= max(lo0, lo1))


# ----------------------------------------------------------------- SISMOS
def sismos(bbox=None, ttl=300):
    """Sismos M2.5+ de las ultimas 24h (USGS). bbox opcional [la_min,lo_min,la_max,lo_max]."""
    def _go():
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
        data = _fetch_json(url)
        if isinstance(data, dict) and data.get("error"):
            return data
        feats = (data or {}).get("features") or []
        out = []
        for f in feats:
            p = f.get("properties") or {}
            g = (f.get("geometry") or {}).get("coordinates") or [None, None, None]
            lon, lat, prof = g[0], g[1], (g[2] if len(g) > 2 else None)
            if lat is None or lon is None:
                continue
            if not _en_bbox(lat, lon, bbox):
                continue
            out.append({
                "mag": p.get("mag"), "lugar": p.get("place"),
                "lat": lat, "lon": lon, "prof_km": prof,
                "cuando": p.get("time"), "url": p.get("url"),
            })
        out.sort(key=lambda s: (s["mag"] if s["mag"] is not None else -9), reverse=True)
        mayor = out[0] if out else None
        return {"count": len(out), "mayor": mayor, "recientes": out[:10]}
    return _cached("sismos:%s" % (bbox,), ttl, _go)


# ------------------------------------------------------- CLIMA ESPACIAL (Kp)
def clima_espacial(ttl=900):
    """Indice Kp planetario (NOAA SWPC). Kp>=5 = tormenta geomagnetica."""
    def _go():
        url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
        data = _fetch_json(url)
        if isinstance(data, dict) and data.get("error"):
            return data
        try:
            filas = data[1:]  # primera fila son encabezados
            ult = filas[-1]
            kp = float(ult[1])
            cuando = ult[0]
        except Exception as exc:
            return {"error": "parseo Kp: %s" % exc}
        if kp >= 7:
            estado = "tormenta geomagnetica fuerte"
        elif kp >= 5:
            estado = "tormenta geomagnetica"
        elif kp >= 4:
            estado = "campo inquieto"
        else:
            estado = "tranquilo"
        return {"kp": kp, "estado": estado, "tormenta": kp >= 5, "cuando": cuando}
    return _cached("kp", ttl, _go)


# ----------------------------------------------------------------- ISS
def iss_pos(ttl=5):
    """Posicion en vivo de la Estacion Espacial Internacional."""
    def _go():
        data = _fetch_json("https://api.wheretheiss.at/v1/satellites/25544")
        if isinstance(data, dict) and data.get("error"):
            return data
        try:
            return {
                "lat": data.get("latitude"), "lon": data.get("longitude"),
                "alt_km": data.get("altitude"), "vel_kmh": data.get("velocity"),
                "visibilidad": data.get("visibility"),
            }
        except Exception as exc:
            return {"error": str(exc)}
    return _cached("iss", ttl, _go)


# ----------------------------------------------------------------- RESUMEN
def _resumen(sis, kp, iss):
    partes = []
    if isinstance(sis, dict) and not sis.get("error"):
        m = sis.get("mayor")
        if m and m.get("mag") is not None:
            partes.append("Sismos 24h: %d (mayor M%.1f en %s)" % (sis["count"], m["mag"], m.get("lugar") or "?"))
        else:
            partes.append("Sismos 24h: %d" % sis.get("count", 0))
    if isinstance(kp, dict) and not kp.get("error"):
        partes.append("Clima espacial Kp %.1f (%s)" % (kp.get("kp", 0), kp.get("estado", "?")))
    if isinstance(iss, dict) and not iss.get("error") and iss.get("lat") is not None:
        partes.append("ISS sobre lat %.1f, lon %.1f" % (float(iss["lat"]), float(iss["lon"])))
    return " | ".join(partes) if partes else "Sin datos del pulso ahora mismo."


def pulso(bbox=None):
    """Pulso del planeta completo (sismos + clima espacial + ISS) con resumen hablado."""
    sis = sismos(bbox)
    kp = clima_espacial()
    iss = iss_pos()
    return {
        "pulso": {"sismos": sis, "clima_espacial": kp, "iss": iss},
        "resumen": _resumen(sis, kp, iss),
        "ts": time.time(),
    }


# ------------------------------------------------- COMPATIBILIDAD (API vieja)
def snapshot(lat_min=-90, lon_min=-180, lat_max=90, lon_max=180):
    """Compatibilidad: ahora devuelve el Pulso del Planeta (sin vuelos ni barcos)."""
    mundo = (lat_min <= -89 and lon_min <= -179 and lat_max >= 89 and lon_max >= 179)
    bbox = None if mundo else [lat_min, lon_min, lat_max, lon_max]
    return pulso(bbox)


def magnetic_available():
    return {"available": False, "reason": "sin sensor magnetometro expuesto al proceso"}
