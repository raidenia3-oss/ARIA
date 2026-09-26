"""
NODO_PHANTOM_OSINT - Extracción sigilosa de metadatos de imágenes públicas.
"""

import os
import time
import logging
import tempfile
import shutil
import requests
from datetime import datetime
from typing import Dict, List
from bs4 import BeautifulSoup
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io
import random

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NOD_PHANTOM_OSINT")

# User-Agents para rotación
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
]

# URL base para búsquedas en DuckDuckGo
SEARCH_URL = "https://duckduckgo.com/html/?q={}&iax=images&ia=images"

def get_random_user_agent():
    """Devuelve un User-Agent aleatorio."""
    return random.choice(USER_AGENTS)

def extract_gps_info(exif_data):
    """Extrae información GPS de los metadatos EXIF."""
    gps_info = {}
    if 'GPSInfo' in exif_data:
        gps_data = exif_data['GPSInfo']
        lat = None
        lon = None

        for tag, value in gps_data.items():
            decoded_tag = GPSTAGS.get(tag, tag)
            if decoded_tag == 'GPSLatitude':
                lat = convert_to_degrees(value)
            elif decoded_tag == 'GPSLongitude':
                lon = convert_to_degrees(value)

        gps_info['lat'] = lat
        gps_info['lon'] = lon

    return gps_info

def convert_to_degrees(value):
    """Convierte coordenadas GPS de formato EXIF a grados decimales."""
    d, m, s = value
    return d + (m / 60.0) + (s / 3600.0)

def extract_exif_data(image_path):
    """Extrae metadatos EXIF de una imagen."""
    exif_data = {}
    try:
        with Image.open(image_path) as img:
            if hasattr(img, '_getexif'):
                exif = img._getexif()
                if exif:
                    for tag, value in exif.items():
                        decoded_tag = TAGS.get(tag, tag)
                        exif_data[decoded_tag] = value
    except Exception as e:
        logger.debug(f"Error al extraer EXIF: {e}")

    return exif_data

def execute(input_data: Dict) -> Dict:
    """
    Ejecuta la extracción sigilosa de metadatos de imágenes públicas.

    INPUT_INTERFACE:
    {
        "target_name": "string",
        "max_images": "int"
    }

    OUTPUT_INTERFACE:
    {
        "target_name": "string",
        "images_analyzed": "int",
        "metadata_found": [{"filename": "string", "gps_lat": "float", "gps_lon": "float", "camera_model": "string", "creation_date": "string"}]
    }
    """
    # Validar entrada
    if not all(key in input_data for key in ['target_name']):
        return {
            "target_name": input_data.get('target_name', ''),
            "images_analyzed": 0,
            "metadata_found": [],
            "error": "Faltan parámetros obligatorios (target_name)"
        }

    target_name = input_data['target_name']
    max_images = input_data.get('max_images', 10)

    # Crear directorio temporal para descargar imágenes
    temp_dir = tempfile.mkdtemp()
    metadata_found = []

    try:
        # Realizar búsqueda en DuckDuckGo
        search_url = SEARCH_URL.format(target_name.replace(" ", "+"))
        headers = {'User-Agent': get_random_user_agent()}

        logger.info(f"🔍 Buscando imágenes para '{target_name}' en DuckDuckGo")
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()

        # Analizar la página de resultados
        soup = BeautifulSoup(response.text, 'html.parser')
        image_elements = soup.find_all('img', {'class': 'tile--img'})

        # Descargar y analizar imágenes
        for i, img_element in enumerate(image_elements[:max_images]):
            try:
                img_url = img_element.get('src')
                if not img_url or not img_url.startswith('http'):
                    continue

                # Descargar imagen
                img_response = requests.get(img_url, headers=headers, timeout=10)
                img_response.raise_for_status()

                # Guardar imagen temporalmente
                img_path = os.path.join(temp_dir, f"img_{i}.jpg")
                with open(img_path, 'wb') as f:
                    f.write(img_response.content)

                # Extraer metadatos EXIF
                exif_data = extract_exif_data(img_path)

                # Procesar metadatos
                metadata = {
                    "filename": f"img_{i}.jpg",
                    "gps_lat": None,
                    "gps_lon": None,
                    "camera_model": None,
                    "creation_date": None
                }

                # Extraer información GPS
                gps_info = extract_gps_info(exif_data)
                if gps_info:
                    metadata["gps_lat"] = gps_info.get('lat')
                    metadata["gps_lon"] = gps_info.get('lon')

                # Extraer modelo de cámara
                if 'Model' in exif_data:
                    metadata["camera_model"] = exif_data['Model']

                # Extraer fecha de creación
                if 'DateTime' in exif_data:
                    metadata["creation_date"] = exif_data['DateTime']
                elif 'DateTimeOriginal' in exif_data:
                    metadata["creation_date"] = exif_data['DateTimeOriginal']

                metadata_found.append(metadata)

            except Exception as e:
                logger.debug(f"Error al procesar imagen {i}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error en la búsqueda de imágenes: {e}")
    finally:
        # Limpiar directorio temporal
        shutil.rmtree(temp_dir)

    return {
        "target_name": target_name,
        "images_analyzed": len(metadata_found),
        "metadata_found": metadata_found
    }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NOD_PHANTOM_OSINT - Extracción de metadatos de imágenes")
    parser.add_argument("target_name", help="Nombre o término de búsqueda para imágenes")
    parser.add_argument("--max-images", type=int, default=10, help="Número máximo de imágenes a analizar")
    args = parser.parse_args()

    input_data = {
        "target_name": args.target_name,
        "max_images": args.max_images
    }

    result = execute(input_data)
    print(result)