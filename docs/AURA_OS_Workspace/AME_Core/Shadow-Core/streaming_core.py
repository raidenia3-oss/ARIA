"""
Módulo para manejar el streaming de datos en tiempo real usando WebSockets.
Integra el modelo LLM (Ollama) y transmite las respuestas token por token.
"""

import asyncio
import json
import websockets
import base64
import io
import tempfile
import os
from ollama_wrapper import OllamaWrapper
from biometric_auth import token_required
import pyttsx3  # Librería para TTS
from chat_db import db
import random

class TTSManager:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)  # Velocidad de lectura
        self.engine.setProperty('volume', 0.9)  # Volumen

    def generate_audio(self, text):
        """
        Genera un archivo de audio a partir del texto.
        """
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_path = temp_file.name

            self.engine.save_to_file(text, temp_path)

            with open(temp_path, 'rb') as audio_file:
                audio_data = base64.b64encode(audio_file.read()).decode('utf-8')

            os.unlink(temp_path)
            return audio_data
        except Exception as e:
            print(f"Error al generar audio: {e}")
            return None

class StreamingWebSocket:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.ollama = OllamaWrapper()
        self.websockets_server = None
        self.tts_manager = TTSManager()
        self.current_conversation_id = None
        self.clients = set()

    async def register(self, websocket):
        """Registra un nuevo cliente WebSocket."""
        self.clients.add(websocket)

    async def unregister(self, websocket):
        """Desregistra un cliente WebSocket."""
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, message):
        """Envía un mensaje a todos los clientes conectados."""
        if not self.clients:
            return

        message_json = json.dumps(message)
        for client in self.clients:
            try:
                await client.send(message_json)
            except Exception as e:
                print(f"Error al enviar mensaje a cliente: {e}")
                await self.unregister(client)

    async def handle_connection(self, websocket, path):
        """
        Maneja la conexión WebSocket y el streaming de respuestas del modelo LLM.
        """
        try:
            await self.register(websocket)

            # Esperar a recibir un mensaje del cliente (prompt)
            message = await websocket.recv()
            data = json.loads(message)

            if not data.get('token'):
                await websocket.send(json.dumps({"error": "Token de autenticación faltante"}))
                return

            prompt = data.get('prompt', '')
            model = data.get('model', 'dolphin-llama3')
            stream = data.get('stream', True)
            tts = data.get('tts', False)
            conversation_id = data.get('conversation_id')

            # Guardar mensaje del usuario
            if conversation_id:
                self.current_conversation_id = conversation_id
                db.add_message(conversation_id, 'user', prompt)

            # Simular eventos aleatorios para pruebas de notificaciones
            if random.random() < 0.1:  # 10% de probabilidad de enviar una alerta de prueba
                await self.broadcast({
                    "eventType": "ALERTA_URGENTE",
                    "title": "Alerta de Prueba",
                    "body": "Se ha detectado una alerta urgente de prueba desde el servidor.",
                    "timestamp": datetime.now().isoformat()
                })

            # Generar respuesta del modelo con streaming
            if stream:
                full_response = ""
                async for chunk in self.ollama.generate_stream(prompt, model):
                    full_response += chunk
                    await websocket.send(chunk)

                if self.current_conversation_id:
                    db.add_message(self.current_conversation_id, 'assistant', full_response)

                if tts and full_response and self.current_conversation_id:
                    # Generar audio TTS
                    audio_data = self.tts_manager.generate_audio(full_response)
                    if audio_data:
                        await websocket.send(json.dumps({"tts": audio_data}))

                # Simular evento de tarea completada
                await self.broadcast({
                    "eventType": "TAREA_COMPLETADA",
                    "title": "Tarea Completada",
                    "body": "La tarea relacionada con tu última consulta ha sido procesada con éxito.",
                    "timestamp": datetime.now().isoformat()
                })

            else:
                response = await self.ollama.generate(prompt, model)
                await websocket.send(json.dumps({"response": response}))

                if self.current_conversation_id:
                    db.add_message(self.current_conversation_id, 'assistant', response)

                if tts and response and self.current_conversation_id:
                    # Generar audio TTS
                    audio_data = self.tts_manager.generate_audio(response)
                    if audio_data:
                        await websocket.send(json.dumps({"tts": audio_data}))

        except json.JSONDecodeError:
            await websocket.send(json.dumps({"error": "Formato de mensaje inválido"}))
        except Exception as e:
            await websocket.send(json.dumps({"error": str(e)}))
        finally:
            await self.unregister(websocket)
            await websocket.close()

    async def start(self):
        """
        Inicia el servidor WebSocket.
        """
        self.websockets_server = await websockets.serve(
            self.handle_connection,
            self.host,
            self.port
        )
        print(f"Servidor WebSocket iniciado en ws://{self.host}:{self.port}")
        await self.websockets_server.wait_closed()

async def main():
    streaming_server = StreamingWebSocket()
    await streaming_server.start()

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())