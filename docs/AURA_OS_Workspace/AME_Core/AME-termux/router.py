import os
import requests
import time

MODELOS = [
    {
        "nombre": "Mistral",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "key": os.getenv("MISTRAL_API_KEY"),
        "modelo": "codestral-latest",
        "tipo": "mistral"
    },
    {
        "nombre": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key": os.getenv("CEREBRAS_API_KEY"),
        "modelo": "llama-3.3-70b",
        "tipo": "openai"
    },
    {
        "nombre": "DeepSeek",
        "url": "https://api.deepseek.com/chat/completions",
        "key": os.getenv("DEEPSEEK_API_KEY"),
        "modelo": "deepseek-chat",
        "tipo": "openai"
    }
]

def consultar(mensaje, historial=[]):
    for modelo in MODELOS:
        try:
            print(f"[AME] Usando: {modelo['nombre']}")
            headers = {
                "Authorization": f"Bearer {modelo['key']}",
                "Content-Type": "application/json"
            }
            mensajes = historial + [{"role": "user", "content": mensaje}]
            body = {
                "model": modelo["modelo"],
                "messages": mensajes,
                "max_tokens": 4096,
                "temperature": 0.7
            }
            respuesta = requests.post(
                modelo["url"],
                headers=headers,
                json=body,
                timeout=30
            )
            if respuesta.status_code == 200:
                contenido = respuesta.json()["choices"][0]["message"]["content"]
                print(f"[AME] Respuesta de {modelo['nombre']} OK")
                return contenido, modelo["nombre"]
            elif respuesta.status_code == 429:
                print(f"[AME] {modelo['nombre']} saturado, cambiando...")
                time.sleep(2)
                continue
            else:
                print(f"[AME] {modelo['nombre']} error {respuesta.status_code}, cambiando...")
                continue
        except requests.exceptions.Timeout:
            print(f"[AME] {modelo['nombre']} timeout, cambiando...")
            continue
        except Exception as e:
            print(f"[AME] {modelo['nombre']} fallo: {e}, cambiando...")
            continue
    return "ERROR: Todos los modelos fallaron.", None

if __name__ == "__main__":
    print("=== AME Router Activo ===")
    print("Modelos: Mistral → Cerebras → DeepSeek")
    print("Escribe 'salir' para cerrar\n")
    historial = []
    while True:
        entrada = input("Tú: ").strip()
        if entrada.lower() == "salir":
            print("[AME] Cerrando...")
            break
        if not entrada:
            continue
        respuesta, modelo_usado = consultar(entrada, historial)
        historial.append({"role": "user", "content": entrada})
        historial.append({"role": "assistant", "content": respuesta})
        print(f"\nAME ({modelo_usado}): {respuesta}\n")
