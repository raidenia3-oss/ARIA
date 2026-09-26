from flask import Flask, request, jsonify
import os, requests, time

app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Servidor AME activo"})

MODELOS = [
    {
        "nombre": "Mistral",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "key": os.getenv("MISTRAL_API_KEY"),
        "modelo": "codestral-latest"
    },
    {
        "nombre": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key": os.getenv("CEREBRAS_API_KEY"),
        "modelo": "llama-3.3-70b"
    },
    {
        "nombre": "DeepSeek",
        "url": "https://api.deepseek.com/chat/completions",
        "key": os.getenv("DEEPSEEK_API_KEY"),
        "modelo": "deepseek-chat"
    }
]

@app.route('/v1/chat/completions', methods=['POST'])
def completions():
    data = request.json
    mensajes = data.get("messages", [])

    for modelo in MODELOS:
        try:
            print(f"[AME] Intentando: {modelo['nombre']}")
            headers = {
                "Authorization": f"Bearer {modelo['key']}",
                "Content-Type": "application/json"
            }
            body = {
                "model": modelo["modelo"],
                "messages": mensajes,
                "max_tokens": data.get("max_tokens", 4096),
                "temperature": data.get("temperature", 0.7)
            }
            r = requests.post(modelo["url"], headers=headers, json=body, timeout=30)
            if r.status_code == 200:
                print(f"[AME] OK con {modelo['nombre']}")
                return jsonify(r.json())
            elif r.status_code == 429:
                print(f"[AME] {modelo['nombre']} saturado, cambiando...")
                time.sleep(2)
                continue
            else:
                print(f"[AME] {modelo['nombre']} error {r.status_code}")
                continue
        except Exception as e:
            print(f"[AME] {modelo['nombre']} fallo: {e}")
            continue

    return jsonify({"error": "Todos los modelos fallaron"}), 500

@app.route('/v1/models', methods=['GET'])
def models():
    return jsonify({
        "data": [{"id": "ame-router", "object": "model"}]
    })

if __name__ == "__main__":
    print("=== AME Servidor activo en puerto 5000 ===")
    app.run(host="0.0.0.0", port=5000)