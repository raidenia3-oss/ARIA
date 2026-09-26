#!/usr/bin/env python3
"""
Proxy para Ollama que permite consultas desde Shadow-Core.
"""

import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434"

@app.route('/ollama/proxy', methods=['POST'])
def ollama_proxy():
    """Proxy para consultas a Ollama."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No se recibió JSON válido"}), 400

        # Redirigir la consulta a Ollama
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"status": "error", "message": "Error en la consulta a Ollama"}), response.status_code

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/ollama/tags', methods=['GET'])
def ollama_tags():
    """Obtener lista de modelos disponibles en Ollama."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags")
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"status": "error", "message": "Error al obtener modelos de Ollama"}), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=False)