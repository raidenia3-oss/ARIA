# AURA_Core/modules/iot_manager.py
# Fase 19: Orquestación Física e IoT (modo simulación por defecto).

from typing import Optional


class IoTManager:
    def __init__(self, simulate: bool = True) -> None:
        self.simulate = simulate

    def _request(self, method: str, url: str, **kwargs):
        if self.simulate:
            return {"ok": True, "mode": "sim", "url": url, "method": method}
        try:
            import requests  # type: ignore

            resp = requests.request(method, url, timeout=10, **kwargs)
            return resp
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def toggle_smart_plug(self, device_id: str, state: bool) -> dict:
        url = f"http://homeassistant.local:8123/api/services/switch/turn_{'on' if state else 'off'}"
        payload = {"entity_id": f"switch.{device_id}"}
        return self._request("POST", url, json=payload)

    def set_ambient_lighting(self, room_id: str, hex_color: str) -> dict:
        url = "https://api.lifx.com/v1/lights/group:{room_id}/state"
        payload = {"color": hex_color, "duration": 0.5}
        return self._request("PUT", url, json=payload)
