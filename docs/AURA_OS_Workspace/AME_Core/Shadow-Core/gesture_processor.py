#!/usr/bin/env python3
"""
Gesture Processor para AURA.
Usa MediaPipe para detectar gestos y enviar eventos a través de Socket.IO.
"""

import cv2
import mediapipe as mp
import numpy as np
import socketio
import threading
import time
from flask import Flask, render_template_string

# Inicializar MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# Configuración de Socket.IO
sio = socketio.Server(cors_allowed_origins='*')
app = Flask(__name__)
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

# Variables globales para el cursor de mano
hand_cursor_position = {"x": 0, "y": 0}
gesture_detected = None
last_gesture_time = 0
gesture_cooldown = 0.5  # Tiempo de espera entre gestos (segundos)

# Definir gestos
GESTURES = {
    "fist": "Cerrar menú",
    "point": "Seleccionar/Mover nodos 3D",
    "none": "Sin gesto"
}

def detect_gesture(hand_landmarks):
    """Detecta el gesto basado en las landmarks de la mano."""
    if not hand_landmarks:
        return "none"

    # Obtener landmarks de la mano
    landmarks = hand_landmarks.landmark

    # Calcular distancia entre el pulgar y el índice para detectar "puño" o "dedo señalando"
    thumb_tip = landmarks[mp_hands.HandLandmark.THUMB_TIP]
    index_finger_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP]

    # Distancia entre el pulgar y el índice
    distance = ((thumb_tip.x - index_finger_tip.x) ** 2 +
                (thumb_tip.y - index_finger_tip.y) ** 2) ** 0.5

    # Si la distancia es pequeña, es un "puño"
    if distance < 0.05:
        return "fist"
    # Si la distancia es grande y el índice está extendido, es "dedo señalando"
    elif index_finger_tip.y < landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP].y:
        return "point"
    else:
        return "none"

def process_hand_landmarks(hand_landmarks):
    """Procesa las landmarks de la mano y actualiza el cursor y el gesto detectado."""
    global hand_cursor_position, gesture_detected, last_gesture_time

    current_time = time.time()
    if current_time - last_gesture_time < gesture_cooldown:
        return

    # Obtener la posición del centro de la mano
    if hand_landmarks:
        landmarks = hand_landmarks.landmark
        center_x = int(landmarks[mp_hands.HandLandmark.WRIST].x * 640)
        center_y = int(landmarks[mp_hands.HandLandmark.WRIST].y * 480)
        hand_cursor_position = {"x": center_x, "y": center_y}

        # Detectar gesto
        gesture = detect_gesture(hand_landmarks)
        if gesture != gesture_detected:
            gesture_detected = gesture
            last_gesture_time = current_time
            print(f"Gesto detectado: {gesture} ({GESTURES[gesture]})")

            # Enviar evento a través de Socket.IO
            sio.emit('gesture_detected', {'gesture': gesture, 'message': GESTURES[gesture]})
    else:
        hand_cursor_position = {"x": 0, "y": 0}

def capture_and_process():
    """Captura video de la webcam y procesa los gestos."""
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Convertir el frame a RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Procesar la imagen con MediaPipe
        results = hands.process(frame_rgb)

        # Dibujar landmarks y cursor de mano
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Dibujar landmarks
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Procesar landmarks
                process_hand_landmarks(hand_landmarks)

        # Dibujar cursor de mano
        if hand_cursor_position["x"] > 0 and hand_cursor_position["y"] > 0:
            cv2.circle(frame, (hand_cursor_position["x"], hand_cursor_position["y"]), 10, (0, 255, 0), -1)

        # Mostrar el frame
        cv2.imshow('Gesture Control', frame)

        # Salir si se presiona 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

@app.route('/')
def index():
    """Página de visualización para el procesador de gestos."""
    return render_template_string('''
        <html>
            <head>
                <title>Gesture Processor</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; }
                    #cursor { position: absolute; width: 20px; height: 20px; background-color: green; border-radius: 50%; }
                </style>
            </head>
            <body>
                <h1>Gesture Processor</h1>
                <p>Detectando gestos...</p>
                <div id="cursor"></div>
                <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
                <script>
                    const socket = io();
                    const cursor = document.getElementById('cursor');

                    socket.on('gesture_position', (data) => {
                        cursor.style.left = `${data.x}px`;
                        cursor.style.top = `${data.y}px`;
                    });

                    socket.on('gesture_detected', (data) => {
                        alert(`Gesto detectado: ${data.message}`);
                    });
                </script>
            </body>
        </html>
    ''')

@sio.event
def connect(sid, environ):
    """Evento de conexión de Socket.IO."""
    print(f"Cliente conectado: {sid}")

@sio.event
def disconnect(sid):
    """Evento de desconexión de Socket.IO."""
    print(f"Cliente desconectado: {sid}")

def start_gesture_processor():
    """Inicia el procesador de gestos en un hilo separado."""
    threading.Thread(target=capture_and_process, daemon=True).start()

if __name__ == "__main__":
    start_gesture_processor()
    app.run(host='0.0.0.0', port=5003, debug=False)