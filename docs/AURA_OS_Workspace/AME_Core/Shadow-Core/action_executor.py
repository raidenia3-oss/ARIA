#!/usr/bin/env python3
"""
Hardware Control Agent y Tactical Operational Tools para AURA.
Permite apagar/reiniciar la PC, tomar capturas de pantalla, gestionar archivos,
y realizar análisis tácticos avanzados con Nmap, Playwright, Pandas, BeautifulSoup,
análisis visual con Vision Engine, Model Router y ahora también Knowledge RAG.
"""

import os
import subprocess
import ctypes
import win32gui
import win32ui
import win32con
import win32api
import time
import json
import uuid
import nmap
import pandas as pd
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import uuid
from selenium import webdriver
from playwright.sync_api import sync_playwright
import tempfile
import shutil
import requests
import re
import cv2
import numpy as np
from PIL import Image
import io
import base64
import tempfile

app = Flask(__name__)

# Configuración de seguridad
AUTH_KEY = "SECRET_AUTH_KEY_12345"  # Reemplaza esto con tu llave de autorización secreta
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'txt', 'log', 'html', 'csv', 'pdf'}
SANDBOX_DIR = os.path.join(os.getcwd(), "AURA_Core", "sandbox")
VISION_ENGINE_URL = "http://localhost:5009"
MODEL_ROUTER_URL = "http://localhost:5011"
KNOWLEDGE_RAG_URL = "http://localhost:5012"

# Crear carpeta de sandbox si no existe
os.makedirs(SANDBOX_DIR, exist_ok=True)

def verify_auth_key(key):
    """Verifica la llave de autorización."""
    return key == AUTH_KEY

def shutdown_pc():
    """Apaga la PC."""
    try:
        ctypes.windll.win32shutdown.WinExec("shutdown /s /t 0", 0)
        return True
    except Exception as e:
        print(f"Error al apagar la PC: {e}")
        return False

def restart_pc():
    """Reinicia la PC."""
    try:
        ctypes.windll.win32shutdown.WinExec("shutdown /r /t 0", 0)
        return True
    except Exception as e:
        print(f"Error al reiniciar la PC: {e}")
        return False

def capture_screen(filename="screenshot.png"):
    """Toma una captura de pantalla y la guarda en un archivo."""
    try:
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

        save_bitmap.SaveBitmapFile(save_dc, filename)

        save_dc.DeleteDC()
        win32gui.ReleaseDC(hdesktop, hwnd)
        win32gui.DeleteObject(save_bitmap.GetHandle())

        return filename
    except Exception as e:
        print(f"Error al tomar captura de pantalla: {e}")
        return None

def list_files(directory="C:\\"):
    """Lista los archivos en un directorio especificado."""
    try:
        files = []
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        return files
    except Exception as e:
        print(f"Error al listar archivos: {e}")
        return []

def allowed_file(filename):
    """Verifica si un archivo tiene una extensión permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_file(file_path, upload_dir="uploads"):
    """Sube un archivo a un directorio de subidas."""
    try:
        os.makedirs(upload_dir, exist_ok=True)
        file_ext = os.path.splitext(file_path)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        upload_path = os.path.join(upload_dir, unique_filename)

        with open(upload_path, 'wb') as f:
            f.write(open(file_path, 'rb').read())

        return unique_filename
    except Exception as e:
        print(f"Error al subir archivo: {e}")
        return None

def run_in_sandbox(script_content, script_name="script.py"):
    """Ejecuta un script en la carpeta de sandboxing."""
    try:
        script_path = os.path.join(SANDBOX_DIR, script_name)
        with open(script_path, 'w') as f:
            f.write(script_content)

        result = subprocess.run(
            ["python", script_path],
            cwd=SANDBOX_DIR,
            capture_output=True,
            text=True
        )

        # Limpiar sandbox después de ejecutar
        os.remove(script_path)

        # Indexar la salida exitosa del comando en Knowledge RAG
        if result.returncode == 0:
            index_successful_command(result.stdout, "script_execution")

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        print(f"Error al ejecutar script en sandbox: {e}")
        return {"error": str(e)}

def perform_nmap_scan(target, arguments="-T4 -F"):
    """Realiza un escaneo de red usando Nmap."""
    try:
        nm = nmap.PortScanner()
        result = nm.scan(hosts=target, arguments=arguments)
        return result
    except Exception as e:
        print(f"Error al realizar escaneo Nmap: {e}")
        return {"error": str(e)}

def scrape_website_with_playwright(url, selector=None):
    """Realiza scraping avanzado de una página web usando Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)

            if selector:
                content = page.inner_text(selector)
            else:
                content = page.content()

            browser.close()
            return content
    except Exception as e:
        print(f"Error al realizar scraping con Playwright: {e}")
        return {"error": str(e)}

def scrape_website_with_selenium(url, selector=None):
    """Realiza scraping avanzado de una página web usando Selenium."""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')

        driver = webdriver.Chrome(options=options)
        driver.get(url)

        if selector:
            element = driver.find_element("css selector", selector)
            content = element.text
        else:
            content = driver.page_source

        driver.quit()
        return content
    except Exception as e:
        print(f"Error al realizar scraping con Selenium: {e}")
        return {"error": str(e)}

def parse_html_with_beautifulsoup(html_content, tag="body"):
    """Parsea contenido HTML usando BeautifulSoup."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.find(tag).get_text()
    except Exception as e:
        print(f"Error al parsear HTML con BeautifulSoup: {e}")
        return {"error": str(e)}

def process_data_with_pandas(data, operation="describe"):
    """Procesa datos usando Pandas."""
    try:
        if isinstance(data, str):
            if data.startswith("<html>"):
                soup = BeautifulSoup(data, 'html.parser')
                tables = soup.find_all('table')
                if tables:
                    df = pd.read_html(str(tables[0]))[0]
                else:
                    return {"error": "No se encontraron tablas en el HTML"}
            elif data.startswith("{") or data.startswith("["):
                df = pd.read_json(data)
            else:
                df = pd.read_csv(pd.compat.StringIO(data))
        else:
            df = pd.DataFrame(data)

        if operation == "describe":
            return df.describe().to_dict()
        elif operation == "head":
            return df.head().to_dict()
        elif operation == "columns":
            return {"columns": list(df.columns)}
        else:
            return {"error": "Operación no soportada"}
    except Exception as e:
        print(f"Error al procesar datos con Pandas: {e}")
        return {"error": str(e)}

def analyze_image_with_vision_engine(image_path, prompt):
    """Analiza una imagen usando el Vision Engine."""
    try:
        # Subir la imagen al Vision Engine
        files = {'file': open(image_path, 'rb')}
        data = {'auth_key': AUTH_KEY, 'prompt': prompt}
        response = requests.post(f"{VISION_ENGINE_URL}/api/vision/upload", files=files, data=data)

        if response.status_code != 200:
            return {"error": f"Error al subir imagen: {response.text}"}

        image_data = response.json()
        image_url = image_data['image_path']

        # Analizar la imagen
        analyze_data = {'auth_key': AUTH_KEY, 'image_path': image_url, 'prompt': prompt}
        analyze_response = requests.post(f"{VISION_ENGINE_URL}/api/vision/analyze", json=analyze_data)

        if analyze_response.status_code != 200:
            return {"error": f"Error al analizar imagen: {analyze_response.text}"}

        return analyze_response.json()['result']
    except Exception as e:
        print(f"Error al analizar imagen con Vision Engine: {e}")
        return {"error": str(e)}

def capture_and_analyze_screen(prompt):
    """Captura la pantalla y la analiza usando el Vision Engine."""
    try:
        # Capturar pantalla
        filename = capture_screen()
        if not filename:
            return {"error": "Error al capturar pantalla"}

        # Analizar la imagen capturada
        result = analyze_image_with_vision_engine(filename, prompt)

        # Limpiar la captura
        os.remove(filename)

        return result
    except Exception as e:
        print(f"Error al capturar y analizar pantalla: {e}")
        return {"error": str(e)}

def diagnose_terminal_errors():
    """Diagnostica errores en la terminal actual."""
    try:
        prompt = "¿Hay algún error en esta terminal?"
        result = capture_and_analyze_screen(prompt)

        if "error" in result:
            return {"status": "error", "message": result["error"]}

        if result.get("status") == "error":
            return result

        return {
            "status": "ok",
            "message": "Análisis de terminal completado.",
            "details": result
        }
    except Exception as e:
        print(f"Error al diagnosticar errores en terminal: {e}")
        return {"error": str(e)}

def analyze_chart_trends():
    """Analiza tendencias en un gráfico."""
    try:
        prompt = "¿Este gráfico muestra alguna tendencia significativa?"
        result = capture_and_analyze_screen(prompt)

        if "error" in result:
            return {"status": "error", "message": result["error"]}

        return {
            "status": "ok",
            "message": "Análisis de gráfico completado.",
            "details": result
        }
    except Exception as e:
        print(f"Error al analizar tendencias en gráfico: {e}")
        return {"error": str(e)}

def query_model_router(prompt, system_prompt=None, options=None):
    """Consultar el Model Router para obtener la mejor respuesta."""
    try:
        data = {
            "prompt": prompt
        }
        if system_prompt:
            data["system_prompt"] = system_prompt
        if options:
            data["options"] = options

        response = requests.post(f"{MODEL_ROUTER_URL}/api/models/route", json=data)
        if response.status_code == 200:
            result = response.json()
            if result["status"] == "ok":
                return {
                    "status": "ok",
                    "model": result["model"],
                    "response": result["response"],
                    "model_load": result.get("model_load", 0),
                    "knowledge_sources": result.get("knowledge_sources", [])
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("message", "Error desconocido"),
                    "selected_model": result.get("selected_model")
                }
        else:
            return {
                "status": "error",
                "message": f"Error al consultar Model Router: {response.text}"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al consultar Model Router: {str(e)}"
        }

def analyze_with_ai(prompt, system_prompt=None):
    """Analizar una consulta usando IA con el modelo más adecuado y conocimiento relevante."""
    return query_model_router(prompt, system_prompt)

def index_successful_command(command_output, command_type="terminal_command"):
    """Indexar la salida exitosa de un comando en Knowledge RAG."""
    try:
        data = {
            "auth_key": AUTH_KEY,
            "command_output": command_output,
            "command_type": command_type
        }
        response = requests.post(f"{KNOWLEDGE_RAG_URL}/api/knowledge/index_command", json=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al indexar comando: {response.text}")
            return {"status": "error", "message": "Error al indexar comando"}
    except Exception as e:
        print(f"Error al indexar comando: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/api/hardware/shutdown', methods=['POST'])
def api_shutdown():
    """Endpoint para apagar la PC."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    if shutdown_pc():
        return jsonify({"status": "ok", "message": "PC apagada correctamente"})
    else:
        return jsonify({"status": "error", "message": "Error al apagar la PC"}), 500

@app.route('/api/hardware/restart', methods=['POST'])
def api_restart():
    """Endpoint para reiniciar la PC."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    if restart_pc():
        return jsonify({"status": "ok", "message": "PC reiniciada correctamente"})
    else:
        return jsonify({"status": "error", "message": "Error al reiniciar la PC"}), 500

@app.route('/api/hardware/capture', methods=['POST'])
def api_capture():
    """Endpoint para tomar una captura de pantalla."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    filename = capture_screen()
    if filename:
        uploaded_filename = upload_file(filename)
        if uploaded_filename:
            return jsonify({"status": "ok", "message": "Captura de pantalla tomada y subida", "filename": uploaded_filename})
        else:
            return jsonify({"status": "error", "message": "Error al subir la captura de pantalla"}), 500
    else:
        return jsonify({"status": "error", "message": "Error al tomar captura de pantalla"}), 500

@app.route('/api/hardware/files', methods=['POST'])
def api_list_files():
    """Endpoint para listar archivos en un directorio."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'directory' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y directorio requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    directory = data['directory']
    files = list_files(directory)
    return jsonify({"status": "ok", "files": files})

@app.route('/api/hardware/upload', methods=['POST'])
def api_upload_file():
    """Endpoint para subir un archivo."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'file_path' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y ruta del archivo requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    file_path = data['file_path']
    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "El archivo no existe"}), 404

    if not allowed_file(file_path):
        return jsonify({"status": "error", "message": "Extensión de archivo no permitida"}), 400

    uploaded_filename = upload_file(file_path)
    if uploaded_filename:
        return jsonify({"status": "ok", "message": "Archivo subido correctamente", "filename": uploaded_filename})
    else:
        return jsonify({"status": "error", "message": "Error al subir el archivo"}), 500

@app.route('/api/tactical/nmap_scan', methods=['POST'])
def api_nmap_scan():
    """Endpoint para realizar un escaneo de red con Nmap."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'target' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y objetivo requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    target = data['target']
    arguments = data.get('arguments', "-T4 -F")
    result = perform_nmap_scan(target, arguments)
    return jsonify({"status": "ok", "result": result})

@app.route('/api/tactical/scrape_playwright', methods=['POST'])
def api_scrape_playwright():
    """Endpoint para realizar scraping con Playwright."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'url' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y URL requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    url = data['url']
    selector = data.get('selector')
    result = scrape_website_with_playwright(url, selector)
    return jsonify({"status": "ok", "result": result})

@app.route('/api/tactical/scrape_selenium', methods=['POST'])
def api_scrape_selenium():
    """Endpoint para realizar scraping con Selenium."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'url' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y URL requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    url = data['url']
    selector = data.get('selector')
    result = scrape_website_with_selenium(url, selector)
    return jsonify({"status": "ok", "result": result})

@app.route('/api/tactical/parse_html', methods=['POST'])
def api_parse_html():
    """Endpoint para parsear HTML con BeautifulSoup."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'html_content' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y contenido HTML requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    html_content = data['html_content']
    tag = data.get('tag', 'body')
    result = parse_html_with_beautifulsoup(html_content, tag)
    return jsonify({"status": "ok", "result": result})

@app.route('/api/tactical/process_data', methods=['POST'])
def api_process_data():
    """Endpoint para procesar datos con Pandas."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'data' not in data or 'operation' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización, datos y operación requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    data_content = data['data']
    operation = data['operation']
    result = process_data_with_pandas(data_content, operation)
    return jsonify({"status": "ok", "result": result})

@app.route('/api/tactical/run_script', methods=['POST'])
def api_run_script():
    """Endpoint para ejecutar un script en la sandbox."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'script' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y script requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    script_content = data['script']
    script_name = data.get('script_name', 'script.py')
    result = run_in_sandbox(script_content, script_name)
    return jsonify({"status": "ok", "result": result})

@app.route('/api/vision/capture_and_analyze', methods=['POST'])
def api_capture_and_analyze():
    """Endpoint para capturar pantalla y analizarla."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y prompt requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    prompt = data['prompt']
    result = capture_and_analyze_screen(prompt)
    return jsonify({"status": "ok", "result": result})

@app.route('/api/vision/diagnose_terminal', methods=['POST'])
def api_diagnose_terminal():
    """Endpoint para diagnosticar errores en la terminal."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    result = diagnose_terminal_errors()
    return jsonify(result)

@app.route('/api/vision/analyze_chart', methods=['POST'])
def api_analyze_chart():
    """Endpoint para analizar tendencias en un gráfico."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    result = analyze_chart_trends()
    return jsonify(result)

@app.route('/api/ai/analyze', methods=['POST'])
def api_ai_analyze():
    """Endpoint para analizar una consulta usando IA con el modelo más adecuado y conocimiento relevante."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y prompt requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    prompt = data['prompt']
    system_prompt = data.get('system_prompt')
    result = analyze_with_ai(prompt, system_prompt)
    return jsonify(result)

@app.route('/api/knowledge/index_command', methods=['POST'])
def api_index_command():
    """Endpoint para indexar la salida de un comando exitoso en Knowledge RAG."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'command_output' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y salida del comando requeridos"}), 400

    if not verify_auth_key(data['auth_key']):
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    command_output = data['command_output']
    command_type = data.get('command_type', 'terminal_command')

    result = index_successful_command(command_output, command_type)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002, debug=False)