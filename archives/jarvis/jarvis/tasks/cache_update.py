import os
import sys
import shutil
import time
import requests

# Resolve paths correctly relative to the project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis_core import JARVISCore

MODELS_DIR = os.path.join(BASE_DIR, 'models')

# Placeholders for future light-weight ONNX model files from Hugging Face Space
MODEL_FILES = {
    "intent_classifier.onnx": "https://huggingface.co/spaces/raidenia3-oss/AURA-inference/resolve/main/models/intent_classifier.onnx",
    "vocab.txt": "https://huggingface.co/spaces/raidenia3-oss/AURA-inference/resolve/main/models/vocab.txt"
}

def get_free_space_gb():
    """Returns free space of the storage partition in GB"""
    usage = shutil.disk_usage(BASE_DIR)
    return usage.free / (1024 ** 3)

def download_file(url, dest_path):
    print(f"Descargando {url} -> {dest_path}")
    # Set a 10-minute timeout for downloads (600 seconds)
    response = requests.get(url, stream=True, timeout=600)
    if response.status_code == 200:
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("✅ Descarga completa.")
        return True
    else:
        print(f"🔴 Error al descargar: HTTP {response.status_code}")
        return False

def sync_models():
    jarvis = JARVISCore()
    # Check connection
    if jarvis.offline:
        print("🔴 Sin internet, abortando descarga de modelos.")
        jarvis.close()
        return

    # Check disk space
    free_gb = get_free_space_gb()
    print(f"Espacio libre en disco: {free_gb:.2f} GB")
    if free_gb < 1.0:
        print("🔴 Abortando: Se requiere al menos 1GB de espacio libre en disco.")
        jarvis.close()
        return

    os.makedirs(MODELS_DIR, exist_ok=True)
    
    # Process each model
    for filename, url in MODEL_FILES.items():
        dest = os.path.join(MODELS_DIR, filename)
        try:
            if not os.path.exists(dest):
                success = download_file(url, dest)
                if not success:
                    # Clean up partial downloads
                    if os.path.exists(dest):
                        os.remove(dest)
            else:
                print(f"El modelo {filename} ya existe localmente.")
        except Exception as e:
            print(f"No se pudo descargar {filename} (opcional en el Space): {e}")
            if os.path.exists(dest):
                os.remove(dest)
            
    jarvis.close()

if __name__ == "__main__":
    print("🤖 Iniciando actualización de modelos locales...")
    try:
        sync_models()
    except KeyboardInterrupt:
        print("\nDescarga interrumpida por el usuario.")
    except Exception as e:
        print(f"\nError fatal: {e}")
