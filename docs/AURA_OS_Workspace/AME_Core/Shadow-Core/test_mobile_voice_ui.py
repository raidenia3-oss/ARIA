#!/usr/bin/env python3
"""
Script de prueba para el Mobile Voice UI.
Simula la interacción con el botón de voz táctico en el navegador.
"""

import os
import sys
import time
import webbrowser
import threading
import http.server
import socketserver
from http import HTTPStatus

# Configuración del servidor de prueba
PORT = 8000
HOST = "localhost"
TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Prueba Mobile Voice UI</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
        }
        .instructions {
            background-color: #e8f5e9;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .button-group {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #45a049;
        }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .status {
            margin: 20px 0;
            padding: 10px;
            border-radius: 4px;
        }
        .success {
            background-color: #e8f5e9;
            color: #2e7d32;
        }
        .error {
            background-color: #ffebee;
            color: #c62828;
        }
        .info {
            background-color: #e3f2fd;
            color: #1976d2;
        }
        .console {
            background-color: #212121;
            color: #e0e0e0;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            max-height: 300px;
            overflow-y: auto;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Prueba Mobile Voice UI</h1>

        <div class="instructions">
            <h2>Instrucciones</h2>
            <p>Este script simula la interacción con el botón de voz táctico en el navegador.</p>
            <p>1. Abre el dashboard de AURA en tu navegador en <code>http://localhost:8000</code></p>
            <p>2. Usa los botones a continuación para simular interacciones con el botón de voz táctico.</p>
            <p>3. Verifica los logs en la consola para ver el estado del sistema.</p>
        </div>

        <div class="button-group">
            <button id="start-recording">Iniciar Grabación</button>
            <button id="stop-recording">Detener Grabación</button>
            <button id="send-audio">Enviar Audio</button>
            <button id="toggle-voice-button">Mostrar/Ocultar Botón de Voz</button>
        </div>

        <div class="status info">
            <h3>Estado Actual</h3>
            <div id="current-status">Botón de voz: Oculto<br>Estado de grabación: No en grabación</div>
        </div>

        <div class="console" id="console-output">
            <p>Iniciando prueba del Mobile Voice UI...</p>
        </div>
    </div>

    <script>
        // Configuración
        const VOICE_BUTTON_VISIBLE = false;
        const IS_RECORDING = false;

        // Elementos del DOM
        const startRecordingBtn = document.getElementById('start-recording');
        const stopRecordingBtn = document.getElementById('stop-recording');
        const sendAudioBtn = document.getElementById('send-audio');
        const toggleVoiceButtonBtn = document.getElementById('toggle-voice-button');
        const currentStatusDiv = document.getElementById('current-status');
        const consoleOutputDiv = document.getElementById('console-output');

        // Estado simulado
        let voiceButtonVisible = VOICE_BUTTON_VISIBLE;
        let isRecording = IS_RECORDING;

        // Funciones para simular interacciones
        function logMessage(message, type = 'info') {
            const logEntry = document.createElement('p');
            logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            logEntry.className = type;
            consoleOutputDiv.appendChild(logEntry);
            consoleOutputDiv.scrollTop = consoleOutputDiv.scrollHeight;
        }

        function updateStatus() {
            currentStatusDiv.innerHTML = `
                Botón de voz: ${voiceButtonVisible ? 'Visible' : 'Oculto'}<br>
                Estado de grabación: ${isRecording ? 'En grabación' : 'No en grabación'}
            `;
        }

        // Simular inicio de grabación
        startRecordingBtn.addEventListener('click', function() {
            if (isRecording) {
                logMessage('Ya se está grabando', 'error');
                return;
            }

            isRecording = true;
            updateStatus();
            logMessage('🎤 Grabación iniciada', 'success');

            // Simular que el botón de voz está visible
            voiceButtonVisible = true;
            updateStatus();

            // Simular animación de pulso
            const pulseIndicator = document.createElement('div');
            pulseIndicator.style.position = 'fixed';
            pulseIndicator.style.bottom = '20px';
            pulseIndicator.style.right = '80px';
            pulseIndicator.style.width = '12px';
            pulseIndicator.style.height = '12px';
            pulseIndicator.style.borderRadius = '50%';
            pulseIndicator.style.backgroundColor = '#F44336';
            pulseIndicator.style.animation = 'pulse 1.5s infinite';
            pulseIndicator.style.zIndex = '9999';
            pulseIndicator.style.boxShadow = '0 0 5px rgba(244, 67, 54, 0.5)';

            document.body.appendChild(pulseIndicator);

            // Eliminar el indicador después de 5 segundos
            setTimeout(() => {
                document.body.removeChild(pulseIndicator);
            }, 5000);

            // Simular visualización de audio
            const audioVisualization = document.createElement('canvas');
            audioVisualization.style.position = 'fixed';
            audioVisualization.style.bottom = '20px';
            audioVisualization.style.left = '50%';
            audioVisualization.style.transform = 'translateX(-50%)';
            audioVisualization.style.width = '120px';
            audioVisualization.style.height = '30px';
            audioVisualization.style.zIndex = '9998';
            audioVisualization.style.marginBottom = '10px';

            document.body.appendChild(audioVisualization);

            // Simular actualización de visualización de audio
            const ctx = audioVisualization.getContext('2d');
            let angle = 0;

            function drawAudioVisualization() {
                if (!isRecording) {
                    document.body.removeChild(audioVisualization);
                    return;
                }

                ctx.clearRect(0, 0, audioVisualization.width, audioVisualization.height);

                // Dibujar barras de audio simuladas
                ctx.fillStyle = 'rgba(255, 87, 34, 0.3)';
                ctx.fillRect(0, 0, audioVisualization.width, audioVisualization.height);

                // Dibujar niveles de audio simulados
                ctx.fillStyle = 'rgba(255, 193, 7, 0.7)';
                ctx.beginPath();

                for (let i = 0; i < 128; i++) {
                    const barHeight = Math.random() * 20 + 5;
                    const x = (i / 128) * audioVisualization.width;
                    const y = audioVisualization.height - barHeight;

                    ctx.fillRect(x, y, audioVisualization.width / 128, barHeight);
                }

                angle += 0.1;
                requestAnimationFrame(drawAudioVisualization);
            }

            drawAudioVisualization();
        });

        // Simular detención de grabación
        stopRecordingBtn.addEventListener('click', function() {
            if (!isRecording) {
                logMessage('No hay grabación en curso', 'error');
                return;
            }

            isRecording = false;
            updateStatus();
            logMessage('🎤 Grabación detenida', 'success');

            // Simular que se envía el audio al servidor
            setTimeout(() => {
                logMessage('📤 Audio enviado al servidor Voice Processor', 'info');
                logMessage('🤖 Procesando comando con el Model Router...', 'info');

                // Simular respuesta del servidor
                setTimeout(() => {
                    logMessage('✅ Comando procesado con éxito!', 'success');
                    logMessage('📝 Texto transcrito: "Escribe un script en Python para analizar datos de tráfico de red"', 'info');
                    logMessage('🤖 Respuesta del sistema: Generando script de análisis de tráfico...', 'info');
                }, 2000);
            }, 1000);
        });

        // Simular envío de audio
        sendAudioBtn.addEventListener('click', function() {
            if (!isRecording) {
                logMessage('No hay audio para enviar. Inicia una grabación primero.', 'error');
                return;
            }

            logMessage('📤 Simulando envío de audio al servidor...', 'info');

            // Simular proceso de envío
            setTimeout(() => {
                logMessage('✅ Audio enviado correctamente al Voice Processor', 'success');
                logMessage('🤖 Procesando con el Swarm Orchestrator...', 'info');

                // Simular respuesta del sistema
                setTimeout(() => {
                    logMessage('🎉 Comando de voz procesado con éxito!', 'success');
                    logMessage('📊 Resultado: Script de análisis de tráfico generado', 'info');
                    logMessage('🔧 Modelo usado: deepseek-coder-v2', 'info');
                }, 3000);
            }, 1500);
        });

        // Simular toggle del botón de voz
        toggleVoiceButtonBtn.addEventListener('click', function() {
            voiceButtonVisible = !voiceButtonVisible;
            updateStatus();
            logMessage(`Botón de voz ${voiceButtonVisible ? 'mostrado' : 'oculto'}`, 'info');
        });

        // Inicializar estado
        updateStatus();
        logMessage('Prueba del Mobile Voice UI lista', 'success');
    </script>

    <style>
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.2); }
            100% { transform: scale(1); }
        }
    </style>
</body>
</html>
"""

class TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(TEST_HTML.encode('utf-8'))
        else:
            super().do_GET()

def run_test_server():
    """Iniciar un servidor de prueba para el Mobile Voice UI."""
    print("🚀 Iniciando servidor de prueba en http://localhost:8000")
    print("Abre tu navegador y ve a http://localhost:8000 para probar el Mobile Voice UI")

    with socketserver.TCPServer((HOST, PORT), TestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Servidor de prueba detenido")
        finally:
            httpd.server_close()

def open_browser():
    """Abrir el navegador en la página de prueba."""
    url = f"http://{HOST}:{PORT}"
    try:
        webbrowser.open(url, new=2)
        print(f"🌐 Abriendo navegador en {url}")
    except Exception as e:
        print(f"⚠️  No se pudo abrir el navegador automáticamente: {e}")
        print(f"Por favor, abre manualmente: {url}")

def main():
    """Función principal para probar el Mobile Voice UI."""
    print("=" * 80)
    print("🎤 PRUEBA DEL MOBILE VOICE UI")
    print("=" * 80)
    print("Este script simula la interacción con el botón de voz táctico en el navegador.")
    print("=" * 80)

    # Iniciar servidor de prueba en un hilo separado
    server_thread = threading.Thread(target=run_test_server, daemon=True)
    server_thread.start()

    # Esperar un momento para que el servidor inicie
    time.sleep(1)

    # Abrir el navegador
    open_browser()

    # Esperar a que el usuario interactúe con la prueba
    print("\n💡 Instrucciones:")
    print("1. Usa los botones en la página de prueba para simular interacciones con el botón de voz táctico.")
    print("2. Verifica los logs en la consola para ver el estado del sistema.")
    print("3. Presiona Ctrl+C para detener el servidor de prueba.")

    # Esperar a que el usuario termine la prueba
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Prueba del Mobile Voice UI finalizada")

if __name__ == "__main__":
    main()