from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import subprocess
from notion_client import Client

app = Flask(__name__)
CORS(app)

# Reemplaza con tu token de Notion copiado
NOTION_TOKEN = "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"
notion = Client(auth=NOTION_TOKEN)

@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "Online", "node": "PC-Master", "notion": "Connected"})

@app.route('/exec', methods=['POST'])
def execute_command():
    data = request.json
    command = data.get('command', '')
    
    if not command:
        return jsonify({"error": "No command provided"}), 400
        
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
        return jsonify({"success": True, "output": output})
    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "output": e.output})

# Endpoint para consultar usuarios/paginas de Notion
@app.route('/notion/users', methods=['GET'])
def get_notion_users():
    try:
        users = notion.users.list()
        return jsonify({"success": True, "data": users})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("🚀 Servidor Puente Ame & Aura activo con soporte Notion en puerto 5000...")
    app.run(host='0.0.0.0', port=5000)
