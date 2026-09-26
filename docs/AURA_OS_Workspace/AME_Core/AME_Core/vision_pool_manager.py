"""
Módulo para gestionar el directorio vision_pool.
Asegura que el directorio exista y proporciona funciones para manejar imágenes.
"""

import os
import time
import uuid
from pathlib import Path

def ensure_vision_pool_exists():
    """
    Asegura que el directorio vision_pool exista.
    """
    vision_pool_dir = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "knowledge_base" / "vision_pool"
    vision_pool_dir.mkdir(parents=True, exist_ok=True)
    return vision_pool_dir

def generate_unique_filename(extension):
    """
    Genera un nombre de archivo único con timestamp y UUID.
    """
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    return f"intel_{timestamp}_{unique_id}.{extension}"

def save_uploaded_file(file_data, vision_pool_dir):
    """
    Guarda un archivo en el directorio vision_pool.
    """
    try:
        # Obtener la extensión del archivo
        filename = file_data.filename
        extension = filename.split('.')[-1].lower()

        # Generar un nombre único
        unique_filename = generate_unique_filename(extension)
        file_path = vision_pool_dir / unique_filename

        # Guardar el archivo
        with open(file_path, 'wb') as f:
            f.write(file_data.read())

        return unique_filename
    except Exception as e:
        print(f"❌ Error guardando archivo: {e}")
        return None