"""Geolocation for ARIA (IP-based, stdlib only, fail-closed)."""
import json
import urllib.request


def locate():
    for url in ("https://ipapi.co/json/", "https://ipwho.is/"):
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            if isinstance(data, dict) and (data.get("latitude") or data.get("lat")):
                return {
                    "ip": data.get("ip"),
                    "city": data.get("city"),
                    "region": data.get("region") or data.get("region_name"),
                    "country": data.get("country_name") or data.get("country"),
                    "lat": data.get("latitude") or data.get("lat"),
                    "lon": data.get("longitude") or data.get("lon"),
                    "timezone": data.get("timezone"),
                    "org": data.get("org") or data.get("isp"),
                }
        except Exception:
            continue
    return {"error": "no se pudo obtener ubicacion"}
