#!/usr/bin/env python3
"""
Servidor MCP para Base de Datos.
Proporciona acceso a la base de datos de AURA.
"""

from flask import Flask, request, jsonify
from AURA_Core.memory_manager import MemoryManager

app = Flask(__name__)
memory_manager = MemoryManager()

@app.route('/api/database/query', methods=['POST'])
def query_database():
    """Consulta la base de datos vectorial."""
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"status": "error", "message": "Consulta requerida"}), 400
    query = data['query']
    try:
        results = memory_manager.query_memory(query)
        return jsonify({
            "status": "ok",
            "results": [
                {"document": doc, "metadata": meta, "score": 1 - score}
                for doc, meta, score in zip(results['documents'], results['metadatas'], results['distances'])
            ]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/database/add', methods=['POST'])
def add_to_database():
    """Añade información a la base de datos vectorial."""
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({"status": "error", "message": "Contenido requerido"}), 400
    content = data['content']
    metadata = data.get('metadata', {})
    try:
        memory_manager.add_memory(content, metadata)
        return jsonify({"status": "ok", "message": "Información añadida a la base de datos"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5007, debug=False)