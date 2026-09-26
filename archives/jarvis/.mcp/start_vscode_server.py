#!/usr/bin/env python3
"""
Servidor MCP para VS Code.
Proporciona contexto de archivos y proyectos en VS Code.
"""

from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/api/vscode/files', methods=['GET'])
def list_vscode_files():
    """Lista archivos en el workspace de VS Code."""
    try:
        workspace_path = os.getenv('VSCODE_WORKSPACE_PATH', os.getcwd())
        files = []
        for root, dirs, filenames in os.walk(workspace_path):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        return jsonify({"status": "ok", "files": files})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/vscode/file_content', methods=['GET'])
def get_file_content():
    """Obtiene el contenido de un archivo."""
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({"status": "error", "message": "Ruta del archivo requerida"}), 400
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"status": "ok", "content": content})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5005, debug=False)