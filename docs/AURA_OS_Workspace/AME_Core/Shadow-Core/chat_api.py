"""
Módulo para manejar los endpoints de la API de conversaciones.
"""

from flask import Flask, request, jsonify
from chat_db import db
from biometric_auth import token_required

app = Flask(__name__)

@app.route('/chats', methods=['GET'])
@token_required
def get_chats():
    """Obtiene la lista de todas las conversaciones."""
    try:
        conversations = db.get_conversations()
        chats = [{
            'id': conv[0],
            'title': conv[1],
            'date': conv[2]
        } for conv in conversations]
        return jsonify({'chats': chats}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chats/<int:chat_id>', methods=['GET'])
@token_required
def get_chat_messages(chat_id):
    """Obtiene los mensajes de una conversación específica."""
    try:
        messages = db.get_messages(chat_id)
        chat_messages = [{
            'role': msg[0],
            'content': msg[1],
            'timestamp': msg[2]
        } for msg in messages]
        return jsonify({'messages': chat_messages}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chats', methods=['POST'])
@token_required
def create_chat():
    """Crea una nueva conversación."""
    try:
        data = request.json
        title = data.get('title', 'Nueva Conversación')
        conversation_id = db.create_conversation(title)
        return jsonify({'id': conversation_id, 'title': title}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/messages', methods=['POST'])
@token_required
def save_message():
    """Guarda un mensaje en una conversación."""
    try:
        data = request.json
        conversation_id = data.get('conversation_id')
        role = data.get('role')
        content = data.get('content')

        if not all([conversation_id, role, content]):
            return jsonify({'error': 'Faltan campos obligatorios'}), 400

        message_id = db.add_message(conversation_id, role, content)
        return jsonify({'id': message_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)