import json
import urllib.error
import urllib.request
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    city = params.get("city", "Buenos Aires")
    url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        current = data.get("current_condition", [{}])[0]
        return {
            "city": city,
            "temp_c": current.get("temp_C"),
            "condition": current.get("weatherDesc", [{}])[0].get("value"),
            "humidity": current.get("humidity"),
        }
    except urllib.error.URLError as e:
        return {"city": city, "temp_c": None, "condition": None, "error": str(e)}
    except Exception as e:
        return {"city": city, "temp_c": None, "condition": None, "error": str(e)}
