import os
import requests
import time
import json
import random

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
if not API_KEY:
    print("⚠️ OPENROUTER_API_KEY no configurada. Usa .env o variable de entorno.")

def call_llm(prompt, retries=3):
    url = "https://openrouter.ai/api/v1/chat/completions"
    data = {"model": "deepseek/deepseek-v4-flash", "messages": [{"role": "user", "content": prompt}]}
    
    for i in range(retries):
        try:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            elif r.status_code in [502, 503, 429]:
                wait = (2 ** i) + random.uniform(0, 0.5)
                print(f" Servidor saturado ({r.status_code}). Reintentando en {wait:.1f}s...")
                time.sleep(wait)
            else:
                return f"Error API: {r.status_code}"
        except Exception as e:
            if i < retries - 1:
                wait = (2 ** i) + random.uniform(0, 0.5)
                print(f"Fallo de conexion: {e}. Reintentando en {wait:.1f}s...")
                time.sleep(wait)
            else:
                print(f"Fallo de conexion: {e}")
    return "Error: No se pudo conectar tras varios intentos."