#!/usr/bin/env python3
"""
Script de prueba para las Notificaciones Proactivas.
Simula el envío de notificaciones de tareas completadas y verifica su recepción.
"""

import os
import sys
import time
import threading
import webbrowser
import http.server
import socketserver
from http import HTTPStatus
import json
import requests
import uuid
from datetime import datetime

# Configuración del servidor de prueba
PORT = 8001
HOST = "localhost"
TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Prueba Notificaciones Proactivas</title>
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
        .notification-log {
            background-color: #212121;
            color: #e0e0e0;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            max-height: 400px;
            overflow-y: auto;
            margin-top: 20px;
        }
        .notification-item {
            padding: 10px;
            border-bottom: 1px solid #444;
            margin-bottom: 5px;
        }
        .notification-item:last-child {
            border-bottom: none;
        }
        .notification-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }
        .notification-time {
            font-size: 12px;
            color: #888;
        }
        .notification-agent {
            font-weight: bold;
            color: #4CAF50;
        }
        .notification-task {
            color: #e0e0e0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Prueba Notificaciones Proactivas</h1>

        <div class="instructions">
            <h2>Instrucciones</h2>
            <p>Este script simula el envío de notificaciones proactivas desde el servidor.</p>
            <p>1. Abre el dashboard de AURA en tu navegador en <code>http://localhost:8001</code></p>
            <p>2. Usa los botones a continuación para simular notificaciones de tareas completadas.</p>
            <p>3. Verifica los logs en la consola y el registro de notificaciones.</p>
        </div>

        <div class="button-group">
            <button id="simulateTaskCompleted">Simular Tarea Completada</button>
            <button id="simulateResearchTask">Simular Investigación Completada</button>
            <button id="simulateCodeTask">Simular Código Generado</button>
            <button id="simulateSwarmActivity">Simular Actividad del Enjambre</button>
            <button id="checkConnection">Verificar Conexión</button>
        </div>

        <div class="status info">
            <h3>Estado Actual</h3>
            <div id="current-status">Conexión: No verificada<br>Notificaciones: No activadas</div>
        </div>

        <div class="console" id="console-output">
            <p>Iniciando prueba de Notificaciones Proactivas...</p>
        </div>

        <div class="notification-log" id="notification-log">
            <h3>Registro de Notificaciones</h3>
            <div id="notification-items">
                <!-- Las notificaciones se añadirán dinámicamente -->
            </div>
        </div>
    </div>

    <script>
        // Configuración global
        const NOTIFICATION_CONFIG = {
            serverUrl: 'http://localhost:5011',
            notificationNamespace: '/notifications',
            testTask: 'Simular tarea compleja de prueba para notificaciones proactivas',
            testResearchTask: 'Investigar las mejores prácticas para optimizar consultas SQL en PostgreSQL',
            testCodeTask: 'Generar un script en Python para analizar datos de tráfico de red',
            testSwarmActivity: {
                agent: 'researcher',
                action: 'investigación completada',
                task: 'Optimización de consultas SQL',
                status: 'completed'
            }
        };

        // Elementos del DOM
        const simulateTaskCompletedBtn = document.getElementById('simulateTaskCompleted');
        const simulateResearchTaskBtn = document.getElementById('simulateResearchTask');
        const simulateCodeTaskBtn = document.getElementById('simulateCodeTask');
        const simulateSwarmActivityBtn = document.getElementById('simulateSwarmActivity');
        const checkConnectionBtn = document.getElementById('checkConnection');
        const currentStatusDiv = document.getElementById('current-status');
        const consoleOutputDiv = document.getElementById('console-output');
        const notificationItemsDiv = document.getElementById('notification-items');

        // Estado de la prueba
        let connectionStatus = 'disconnected';
        let notificationSocket = null;
        let notificationCount = 0;

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
                Conexión: ${connectionStatus === 'connected' ? 'Conectada' : 'No conectada'}<br>
                Notificaciones: ${notificationCount > 0 ? `${notificationCount} recibidas` : 'No activadas'}
            `;
        }

        // Conectar al servidor WebSocket para notificaciones
        function connectToNotificationSocket() {
            if ('WebSocket' in window) {
                try {
                    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = `${wsProtocol}//${window.location.hostname}:5011${NOTIFICATION_CONFIG.notificationNamespace}`;

                    logMessage(`🔔 Conectando a WebSocket para notificaciones: ${wsUrl}`);

                    notificationSocket = new WebSocket(wsUrl);

                    notificationSocket.onopen = function() {
                        logMessage('🔔 Conexión WebSocket establecida');
                        connectionStatus = 'connected';
                        updateStatus();

                        // Enviar mensaje de suscripción
                        notificationSocket.send(JSON.stringify({
                            action: 'subscribe',
                            channel: 'task_completed',
                            user_id: 'test_user'
                        }));

                        logMessage('🔔 Suscrito a notificaciones de tareas completadas');
                    };

                    notificationSocket.onmessage = function(event) {
                        try {
                            const data = JSON.parse(event.data);
                            logMessage(`🔔 Mensaje recibido: ${data.type}`, 'info');

                            if (data.type === 'TASK_COMPLETED') {
                                handleTaskCompletedNotification(data);
                            } else if (data.type === 'swarm_activity') {
                                handleSwarmActivityNotification(data.activity);
                            } else if (data.type === 'agent_status_update') {
                                logMessage(`🔔 Estado del agente actualizado: ${data.swarm_status}`, 'info');
                            } else if (data.type === 'subscription_confirmation') {
                                logMessage(`🔔 Suscripción confirmada: ${data.channel}`, 'success');
                            }
                        } catch (error) {
                            logMessage(`❌ Error al parsear mensaje WebSocket: ${error.message}`, 'error');
                        }
                    };

                    notificationSocket.onclose = function() {
                        logMessage('🔔 Conexión WebSocket cerrada', 'warning');
                        connectionStatus = 'disconnected';
                        updateStatus();

                        // Reintentar conexión después de 5 segundos
                        setTimeout(connectToNotificationSocket, 5000);
                    };

                    notificationSocket.onerror = function(error) {
                        logMessage(`❌ Error en WebSocket: ${error.message}`, 'error');
                        connectionStatus = 'disconnected';
                        updateStatus();

                        // Reintentar conexión después de 5 segundos
                        setTimeout(connectToNotificationSocket, 5000);
                    };

                } catch (error) {
                    logMessage(`❌ Error al conectar a WebSocket: ${error.message}`, 'error');
                    connectionStatus = 'disconnected';
                    updateStatus();
                }
            } else {
                logMessage('⚠️  WebSocket no soportado en este navegador', 'warning');
                connectionStatus = 'unsupported';
                updateStatus();
            }
        }

        // Manejar notificación de tarea completada
        function handleTaskCompletedNotification(data) {
            notificationCount++;
            updateStatus();

            const notificationItem = document.createElement('div');
            notificationItem.className = 'notification-item';

            const header = document.createElement('div');
            header.className = 'notification-header';

            const timeElement = document.createElement('span');
            timeElement.className = 'notification-time';
            timeElement.textContent = new Date(data.timestamp).toLocaleTimeString();

            const agentElement = document.createElement('span');
            agentElement.className = 'notification-agent';
            agentElement.textContent = data.agent;

            header.appendChild(timeElement);
            header.appendChild(agentElement);

            const taskElement = document.createElement('div');
            taskElement.className = 'notification-task';
            taskElement.textContent = data.task;

            const detailsElement = document.createElement('div');
            detailsElement.textContent = data.response_summary || 'Tarea completada con éxito';

            notificationItem.appendChild(header);
            notificationItem.appendChild(taskElement);
            notificationItem.appendChild(detailsElement);

            notificationItemsDiv.insertBefore(notificationItem, notificationItemsDiv.firstChild);

            logMessage(`🔔 Tarea completada por ${data.agent}: ${data.task}`, 'success');
        }

        // Manejar notificación de actividad del enjambre
        function handleSwarmActivityNotification(activity) {
            notificationCount++;
            updateStatus();

            const notificationItem = document.createElement('div');
            notificationItem.className = 'notification-item';

            const header = document.createElement('div');
            header.className = 'notification-header';

            const timeElement = document.createElement('span');
            timeElement.className = 'notification-time';
            timeElement.textContent = new Date(activity.timestamp).toLocaleTimeString();

            const agentElement = document.createElement('span');
            agentElement.className = 'notification-agent';
            agentElement.textContent = activity.agent;

            header.appendChild(timeElement);
            header.appendChild(agentElement);

            const actionElement = document.createElement('div');
            actionElement.textContent = activity.action;

            const taskElement = document.createElement('div');
            taskElement.textContent = activity.task || 'Actividad del enjambre';

            notificationItem.appendChild(header);
            notificationItem.appendChild(actionElement);
            notificationItem.appendChild(taskElement);

            notificationItemsDiv.insertBefore(notificationItem, notificationItemsDiv.firstChild);

            logMessage(`🔔 Actividad del enjambre: ${activity.agent} - ${activity.action}`, 'info');
        }

        // Simular tarea completada
        function simulateTaskCompleted() {
            if (connectionStatus !== 'connected') {
                logMessage('⚠️  No hay conexión establecida con el servidor', 'warning');
                return;
            }

            const taskData = {
                type: 'TASK_COMPLETED',
                timestamp: new Date().toISOString(),
                agent: 'generalist',
                task: NOTIFICATION_CONFIG.testTask,
                task_type: 'GENERAL_TASK',
                response_summary: 'El sistema ha procesado la tarea y generado una respuesta completa con múltiples perspectivas.',
                model: 'llama3',
                status: 'completed'
            };

            logMessage('📤 Simulando notificación de tarea completada...', 'info');

            // Enviar notificación al servidor (simulando lo que haría el backend)
            fetch('http://localhost:5011/api/simulate-notification', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(taskData)
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Error al enviar notificación simulada');
                }
            })
            .then(data => {
                logMessage('✅ Notificación simulada enviada al servidor', 'success');
            })
            .catch(error => {
                logMessage(`❌ Error al enviar notificación simulada: ${error.message}`, 'error');
            });
        }

        // Simular investigación completada
        function simulateResearchTask() {
            if (connectionStatus !== 'connected') {
                logMessage('⚠️  No hay conexión establecida con el servidor', 'warning');
                return;
            }

            const taskData = {
                type: 'TASK_COMPLETED',
                timestamp: new Date().toISOString(),
                agent: 'researcher',
                task: NOTIFICATION_CONFIG.testResearchTask,
                task_type: 'RESEARCH_TASK',
                response_summary: 'Investigación completada con análisis detallado de optimización de consultas SQL en PostgreSQL.',
                model: 'dolphin-llama3',
                status: 'completed'
            };

            logMessage('📤 Simulando notificación de investigación completada...', 'info');

            fetch('http://localhost:5011/api/simulate-notification', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(taskData)
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Error al enviar notificación simulada');
                }
            })
            .then(data => {
                logMessage('✅ Notificación de investigación enviada al servidor', 'success');
            })
            .catch(error => {
                logMessage(`❌ Error al enviar notificación de investigación: ${error.message}`, 'error');
            });
        }

        // Simular código generado
        function simulateCodeTask() {
            if (connectionStatus !== 'connected') {
                logMessage('⚠️  No hay conexión establecida con el servidor', 'warning');
                return;
            }

            const taskData = {
                type: 'TASK_COMPLETED',
                timestamp: new Date().toISOString(),
                agent: 'coder',
                task: NOTIFICATION_CONFIG.testCodeTask,
                task_type: 'CODE_TASK',
                response_summary: 'Script generado para análisis de tráfico de red con visualización en tiempo real.',
                model: 'deepseek-coder-v2',
                status: 'completed'
            };

            logMessage('📤 Simulando notificación de código generado...', 'info');

            fetch('http://localhost:5011/api/simulate-notification', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(taskData)
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Error al enviar notificación simulada');
                }
            })
            .then(data => {
                logMessage('✅ Notificación de código generado enviada al servidor', 'success');
            })
            .catch(error => {
                logMessage(`❌ Error al enviar notificación de código: ${error.message}`, 'error');
            });
        }

        // Simular actividad del enjambre
        function simulateSwarmActivity() {
            if (connectionStatus !== 'connected') {
                logMessage('⚠️  No hay conexión establecida con el servidor', 'warning');
                return;
            }

            const activityData = {
                type: 'swarm_activity',
                activity: {
                    timestamp: new Date().toISOString(),
                    agent: NOTIFICATION_CONFIG.testSwarmActivity.agent,
                    action: NOTIFICATION_CONFIG.testSwarmActivity.action,
                    task: NOTIFICATION_CONFIG.testSwarmActivity.task,
                    status: NOTIFICATION_CONFIG.testSwarmActivity.status,
                    details: 'El agente ha completado su parte de la tarea del enjambre.'
                }
            };

            logMessage('📤 Simulando notificación de actividad del enjambre...', 'info');

            fetch('http://localhost:5011/api/simulate-swarm-activity', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(activityData)
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Error al enviar actividad simulada');
                }
            })
            .then(data => {
                logMessage('✅ Actividad del enjambre enviada al servidor', 'success');
            })
            .catch(error => {
                logMessage(`❌ Error al enviar actividad del enjambre: ${error.message}`, 'error');
            });
        }

        // Verificar conexión
        function checkConnectionStatus() {
            logMessage('🔍 Verificando conexión con el servidor...', 'info');

            fetch('http://localhost:5011/api/models')
                .then(response => {
                    if (response.ok) {
                        return response.json();
                    } else {
                        throw new Error('Error al verificar conexión');
                    }
                })
                .then(data => {
                    logMessage('✅ Conexión con el servidor verificada', 'success');
                    logMessage(`📊 Modelos disponibles: ${Object.keys(data.models || {}).length}`, 'info');
                    logMessage(`🌐 Modo offline: ${data.offline_mode ? 'Activado' : 'Desactivado'}`, 'info');
                })
                .catch(error => {
                    logMessage(`❌ Error al verificar conexión: ${error.message}`, 'error');
                });
        }

        // Configurar eventos para los botones
        simulateTaskCompletedBtn.addEventListener('click', simulateTaskCompleted);
        simulateResearchTaskBtn.addEventListener('click', simulateResearchTask);
        simulateCodeTaskBtn.addEventListener('click', simulateCodeTask);
        simulateSwarmActivityBtn.addEventListener('click', simulateSwarmActivity);
        checkConnectionBtn.addEventListener('click', checkConnectionStatus);

        // Inicializar estado
        updateStatus();
        logMessage('Prueba de Notificaciones Proactivas lista', 'success');

        // Conectar al WebSocket cuando el DOM esté listo
        document.addEventListener('DOMContentLoaded', function() {
            connectToNotificationSocket();
        });
    </script>
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

    def do_POST(self):
        if self.path == '/api/simulate-notification':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # Simular procesamiento del servidor
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": "Notificación simulada procesada",
                "data": data
            }).encode('utf-8'))

        elif self.path == '/api/simulate-swarm-activity':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # Simular procesamiento del servidor
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": "Actividad del enjambre simulada procesada",
                "data": data
            }).encode('utf-8'))

        else:
            super().do_POST()

def run_test_server():
    """Iniciar un servidor de prueba para las Notificaciones Proactivas."""
    print("🚀 Iniciando servidor de prueba en http://localhost:8001")
    print("Abre tu navegador y ve a http://localhost:8001 para probar las Notificaciones Proactivas")

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
    """Función principal para probar las Notificaciones Proactivas."""
    print("=" * 80)
    print("🔔 PRUEBA DE NOTIFICACIONES PROACTIVAS")
    print("=" * 80)
    print("Este script simula el envío de notificaciones proactivas desde el servidor.")
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
    print("1. Usa los botones en la página de prueba para simular notificaciones.")
    print("2. Verifica los logs en la consola y el registro de notificaciones.")
    print("3. Presiona Ctrl+C para detener el servidor de prueba.")

    # Esperar a que el usuario termine la prueba
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Prueba de Notificaciones Proactivas finalizada")

if __name__ == "__main__":
    main()