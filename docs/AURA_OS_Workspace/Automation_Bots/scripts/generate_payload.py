import json

payload = {
    "prompt": "¿Cómo puedo mejorar la seguridad en un sistema de OSINT como AURA?"
}

with open("temp_payload.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=4)