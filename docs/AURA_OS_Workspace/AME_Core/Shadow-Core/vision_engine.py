#!/usr/bin/env python3
"""
Vision Engine para AURA.
Procesa imágenes, captura frames de pantalla y analiza contenido visual usando Ollama.
"""

import os
import cv2
import numpy as np
import base64
import subprocess
import json
import time
from flask import Flask, request, jsonify
from PIL import Image
import io
import tempfile
import uuid

app = Flask(__name__)

# Configuración global
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def capture_screen(filename="screen_capture.png"):
    """Captura la pantalla y guarda la imagen."""
    try:
        # Usar win32api para capturar la pantalla
        import win32gui
        import win32ui
        import win32con
        import win32api

        hdesktop = win32gui.GetDesktopWindow()
        width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        hwnd = win32gui.GetWindowDC(hdesktop)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd)
        save_dc = mfc_dc.CreateCompatibleDC()

        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)

        save_dc.SelectObject(save_bitmap)
        save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)

        img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1
        )

        img.save(os.path.join(UPLOAD_FOLDER, filename))
        save_dc.DeleteDC()
        win32gui.ReleaseDC(hdesktop, hwnd)
        win32gui.DeleteObject(save_bitmap.GetHandle())

        return os.path.join(UPLOAD_FOLDER, filename)
    except Exception as e:
        print(f"Error al capturar pantalla: {e}")
        return None

def image_to_base64(image_path):
    """Convierte una imagen a base64 para enviar a Ollama."""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_string

def analyze_image_with_ollama(image_path, prompt):
    """Analiza una imagen usando Ollama con un modelo multimodal."""
    try:
        # Convertir la imagen a base64
        base64_image = image_to_base64(image_path)

        # Crear el prompt para Ollama
        ollama_prompt = f"""
        Analiza la siguiente imagen y responde a la pregunta:

        <image>{base64_image}</image>

        Pregunta: {prompt}

        Respuesta:
        """

        # Ejecutar Ollama para obtener la descripción
        result = subprocess.run(
            ["ollama", "run", "llava", "--prompt", ollama_prompt],
            capture_output=True,
            text=True,
            check=True
        )

        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error al analizar imagen con Ollama: {e.stderr}")
        return f"Error al procesar la imagen: {e.stderr}"
    except Exception as e:
        print(f"Error general al analizar imagen: {e}")
        return f"Error general: {str(e)}"

def detect_errors_in_terminal(image_path):
    """Detecta errores en una captura de terminal."""
    try:
        # Usar Tesseract OCR para extraer texto de la terminal
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)

        # Analizar el texto en busca de errores comunes
        error_patterns = [
            r"Error:",
            r"Exception:",
            r"Traceback",
            r"Failed to",
            r"TimeoutError",
            r"ConnectionError",
            r"ValueError",
            r"TypeError",
            r"IndexError",
            r"KeyError",
            r"AttributeError",
            r"SyntaxError",
            r"IndentationError",
            r"ModuleNotFoundError",
            r"ImportError"
        ]

        errors_found = []
        for pattern in error_patterns:
            if re.search(pattern, text):
                errors_found.append(pattern)

        if errors_found:
            return {
                "status": "error",
                "message": f"Se detectaron errores en la terminal: {', '.join(errors_found)}",
                "suggested_actions": [
                    "Revisar los logs del sistema.",
                    "Ejecutar el comando nuevamente con depuración habilitada.",
                    "Consultar la documentación técnica."
                ]
            }
        else:
            return {
                "status": "ok",
                "message": "No se detectaron errores en la terminal."
            }
    except Exception as e:
        print(f"Error al detectar errores en terminal: {e}")
        return {
            "status": "error",
            "message": f"Error al procesar la imagen de la terminal: {str(e)}"
        }

def analyze_chart(image_path):
    """Analiza un gráfico en la imagen y describe tendencias."""
    try:
        description = analyze_image_with_ollama(image_path, "Describe las tendencias en este gráfico.")
        return {
            "status": "ok",
            "description": description,
            "analysis": analyze_trends(description)
        }
    except Exception as e:
        print(f"Error al analizar gráfico: {e}")
        return {
            "status": "error",
            "message": f"Error al analizar el gráfico: {str(e)}"
        }

def analyze_trends(description):
    """Analiza tendencias en la descripción de un gráfico."""
    trends = {
        "increasing": False,
        "decreasing": False,
        "stable": False,
        "spikes": False,
        "drops": False
    }

    description_lower = description.lower()

    if "aumentando" in description_lower or "subiendo" in description_lower or "incremento" in description_lower:
        trends["increasing"] = True
    elif "disminuyendo" in description_lower or "bajando" in description_lower or "decremento" in description_lower:
        trends["decreasing"] = True
    elif "estable" in description_lower or "constante" in description_lower:
        trends["stable"] = True
    elif "pico" in description_lower or "picos" in description_lower or "punto máximo" in description_lower:
        trends["spikes"] = True
    elif "caída" in description_lower or "mínimo" in description_lower or "dip" in description_lower:
        trends["drops"] = True

    return trends

@app.route('/api/vision/capture', methods=['POST'])
def capture_image():
    """Endpoint para capturar la pantalla."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    filename = f"screen_capture_{int(time.time())}.png"
    image_path = capture_screen(filename)

    if image_path:
        return jsonify({
            "status": "ok",
            "message": "Pantalla capturada correctamente",
            "image_path": image_path
        })
    else:
        return jsonify({"status": "error", "message": "Error al capturar la pantalla"}), 500

@app.route('/api/vision/analyze', methods=['POST'])
def analyze_image():
    """Endpoint para analizar una imagen."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'image_path' not in data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización, ruta de imagen y prompt requeridos"}), 400

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    image_path = data['image_path']
    prompt = data['prompt']

    if not os.path.exists(image_path):
        return jsonify({"status": "error", "message": "Ruta de imagen no válida"}), 400

    if prompt.lower().startswith("¿hay algún error en esta terminal?"):
        result = detect_errors_in_terminal(image_path)
    elif prompt.lower().startswith("¿este gráfico muestra"):
        result = analyze_chart(image_path)
    else:
        result = analyze_image_with_ollama(image_path, prompt)

    return jsonify({
        "status": "ok",
        "result": result
    })

@app.route('/api/vision/upload', methods=['POST'])
def upload_image():
    """Endpoint para subir una imagen desde un dispositivo externo."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No se proporcionó archivo"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400

    if file:
        filename = f"uploaded_image_{uuid.uuid4().hex}{os.path.splitext(file.filename)[1]}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        return jsonify({
            "status": "ok",
            "message": "Imagen subida correctamente",
            "image_path": filepath
        })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5009, debug=False)