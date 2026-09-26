"""
NODO_PHANTOM_OSINT - Rastreador sigiloso de metadatos de imágenes públicas.

ESTRUCTURA:
- NODE_ID: NOD_PHANTOM_OSINT
- INPUT_INTERFACE: {'target': str, 'search_engines': list, 'max_images': int, 'depth': int}
- CORE_LOGIC: Búsqueda sigilosa en motores de búsqueda de imágenes y extracción de metadatos
- OUTPUT_INTERFACE: {
    'target': str,
    'status': str,
    'images_found': int,
    'images_analyzed': int,
    'metadata_extracted': list,
    'sources': dict,
    'timestamp': str,
    'metadata': dict
}
"""

import json
import re
import requests
import exifread
import base64
import io
import platform
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse, quote
import hashlib
import os
from bs4 import BeautifulSoup
import mimetypes

# Importar la clase base de nodos tácticos
from Shadow-Core.Nodes.node_base import TacticalNode, logger

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuración del módulo
DEFAULT_MAX_IMAGES = 20
DEFAULT_DEPTH = 2
DEFAULT_SEARCH_ENGINES = [
    "https://www.google.com/searchbyimage?image_url={}",
    "https://www.bing.com/images/search?q={}",
    "https://www.yandex.ru/images/search?text={}",
    "https://www.baidu.com/s?wd={}&tn=baiduimage"
]

class NOD_PHANTOM_OSINT(TacticalNode):
    """
    Nodo avanzado para extracción sigilosa de metadatos de imágenes públicas.
    """

    def __init__(self):
        super().__init__()
        self.node_id = "NOD_PHANTOM_OSINT"
        self.version = "1.0.0"
        self.status = "inactive"
        self._initialized = False
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        self.headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def validate_input(self, input_data: Dict) -> bool:
        """
        Valida la entrada del nodo según el INPUT_INTERFACE.
        """
        required_fields = ['target']
        for field in required_fields:
            if field not in input_data:
                logger.error(f"❌ Campo requerido faltante: {field}")
                return False

        if not isinstance(input_data.get('target'), str):
            logger.error("❌ target debe ser un string (nombre, término de búsqueda o URL)")
            return False

        if not input_data.get('max_images', DEFAULT_MAX_IMAGES) > 0:
            logger.error("❌ max_images debe ser un número positivo")
            return False

        if not input_data.get('depth', DEFAULT_DEPTH) > 0:
            logger.error("❌ depth debe ser un número positivo")
            return False

        return True

    def _sanitize_search_term(self, term: str) -> str:
        """
        Sanitiza un término de búsqueda para motores de búsqueda.
        """
        # Eliminar caracteres especiales que puedan romper la búsqueda
        sanitized = re.sub(r'[^\w\s\-]', '', term)
        # Reemplazar espacios por +
        sanitized = sanitized.replace(' ', '+')
        return sanitized

    def _extract_image_urls_from_page(self, url: str, search_term: str) -> List[str]:
        """
        Extrae URLs de imágenes de una página de resultados de búsqueda.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            image_urls = set()

            # Extraer imágenes de diferentes fuentes según el motor de búsqueda
            if 'google' in url:
                # Google Images
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower()):
                        # Resolver URLs relativas
                        if not src.startswith(('http://', 'https://')):
                            src = urlparse(url).scheme + '://' + urlparse(url).netloc + src
                        image_urls.add(src)

                # Buscar en elementos con datos de imágenes
                for element in soup.find_all(['a', 'div'], attrs={'data-src': True}):
                    src = element.get('data-src')
                    if src and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower()):
                        if not src.startswith(('http://', 'https://')):
                            src = urlparse(url).scheme + '://' + urlparse(url).netloc + src
                        image_urls.add(src)

            elif 'bing' in url:
                # Bing Images
                for img in soup.find_all('img', {'class': re.compile(r'mimg|img')}):
                    src = img.get('src')
                    if src and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower()):
                        if not src.startswith(('http://', 'https://')):
                            src = urlparse(url).scheme + '://' + urlparse(url).netloc + src
                        image_urls.add(src)

            elif 'yandex' in url:
                # Yandex Images
                for img in soup.find_all('img', {'class': re.compile(r'serp-item__thumb|thumb')}):
                    src = img.get('src')
                    if src and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower()):
                        if not src.startswith(('http://', 'https://')):
                            src = urlparse(url).scheme + '://' + urlparse(url).netloc + src
                        image_urls.add(src)

            elif 'baidu' in url:
                # Baidu Images
                for img in soup.find_all('img', {'class': re.compile(r'img')}):
                    src = img.get('src')
                    if src and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower()):
                        if not src.startswith(('http://', 'https://')):
                            src = urlparse(url).scheme + '://' + urlparse(url).netloc + src
                        image_urls.add(src)

            return list(image_urls)

        except Exception as e:
            logger.error(f"❌ Error al extraer imágenes de {url}: {e}")
            return []

    def _search_images(self, search_term: str, search_engines: List[str] = None) -> List[str]:
        """
        Realiza búsquedas de imágenes en múltiples motores de búsqueda.
        """
        if search_engines is None:
            search_engines = DEFAULT_SEARCH_ENGINES

        image_urls = set()
        sanitized_term = self._sanitize_search_term(search_term)

        for engine in search_engines:
            try:
                # Reemplazar placeholders en la URL del motor de búsqueda
                search_url = engine.format(quote(sanitized_term))

                logger.info(f"🔍 Buscando imágenes en {engine} para término: {search_term}")

                # Extraer imágenes de la primera página de resultados
                urls = self._extract_image_urls_from_page(search_url, search_term)
                if urls:
                    image_urls.update(urls)

                    # Limitar el número de imágenes
                    if len(image_urls) >= DEFAULT_MAX_IMAGES:
                        break

            except Exception as e:
                logger.error(f"❌ Error al buscar en {engine}: {e}")
                continue

        return list(image_urls)

    def _download_image(self, url: str) -> Optional[bytes]:
        """
        Descarga una imagen desde una URL.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10, stream=True)
            response.raise_for_status()

            # Verificar que el contenido sea una imagen
            content_type = response.headers.get('content-type', '')
            if not any(ext in content_type.lower() for ext in ['jpeg', 'jpg', 'png', 'gif', 'webp']):
                return None

            return response.content

        except Exception as e:
            logger.error(f"❌ Error al descargar imagen desde {url}: {e}")
            return None

    def _extract_metadata(self, image_data: bytes) -> Dict:
        """
        Extrae metadatos de una imagen usando exifread y técnicas adicionales.
        """
        metadata = {
            'image_hash': None,
            'file_type': None,
            'size': None,
            'dimensions': None,
            'exif': {},
            'xmp': {},
            'iptc': {},
            'other': {}
        }

        try:
            # Calcular hash de la imagen
            image_hash = hashlib.sha256(image_data).hexdigest()
            metadata['image_hash'] = image_hash

            # Determinar tipo de archivo
            file_type, _ = mimetypes.guess_type(image_data)
            metadata['file_type'] = file_type

            # Obtener tamaño
            metadata['size'] = len(image_data)

            # Intentar extraer metadatos con exifread
            try:
                tags = exifread.process_file(io.BytesIO(image_data), details=False)

                for tag, value in tags.items():
                    if not isinstance(value, exifread.utils.Ratio):
                        metadata['exif'][tag] = str(value)
                    else:
                        metadata['exif'][tag] = f"{value.numerator}/{value.denominator}"

                # Extraer dimensiones si están disponibles
                if 'EXIF ImageWidth' in metadata['exif'] and 'EXIF ImageLength' in metadata['exif']:
                    width = int(metadata['exif']['EXIF ImageWidth'].split('/')[0])
                    height = int(metadata['exif']['EXIF ImageLength'].split('/')[0])
                    metadata['dimensions'] = {'width': width, 'height': height}

            except Exception as e:
                logger.debug(f"⚠️ Error al extraer metadatos EXIF: {e}")

            # Intentar extraer metadatos XMP (requiere libxmp)
            try:
                # Este es un placeholder - en un entorno real usaríamos una librería como xmp-toolkit
                pass
            except Exception as e:
                logger.debug(f"⚠️ Error al extraer metadatos XMP: {e}")

            # Intentar extraer metadatos IPTC (requiere libiptcdata)
            try:
                # Este es un placeholder - en un entorno real usaríamos una librería como iptcinfo
                pass
            except Exception as e:
                logger.debug(f"⚠️ Error al extraer metadatos IPTC: {e}")

            # Extraer metadatos adicionales
            metadata['other']['creation_date'] = self._extract_creation_date(metadata['exif'])
            metadata['other']['camera_make'] = self._extract_camera_make(metadata['exif'])
            metadata['other']['camera_model'] = self._extract_camera_model(metadata['exif'])
            metadata['other']['software'] = self._extract_software(metadata['exif'])

        except Exception as e:
            logger.error(f"❌ Error al procesar metadatos de imagen: {e}")

        return metadata

    def _extract_creation_date(self, exif_data: Dict) -> Optional[str]:
        """Extrae la fecha de creación de la imagen."""
        if 'EXIF DateTimeOriginal' in exif_data:
            return exif_data['EXIF DateTimeOriginal']
        elif 'Image DateTime' in exif_data:
            return exif_data['Image DateTime']
        elif 'EXIF DateTimeDigitized' in exif_data:
            return exif_data['EXIF DateTimeDigitized']
        return None

    def _extract_camera_make(self, exif_data: Dict) -> Optional[str]:
        """Extrae la marca de la cámara."""
        if 'EXIF Make' in exif_data:
            return exif_data['EXIF Make']
        return None

    def _extract_camera_model(self, exif_data: Dict) -> Optional[str]:
        """Extrae el modelo de la cámara."""
        if 'EXIF Model' in exif_data:
            return exif_data['EXIF Model']
        return None

    def _extract_software(self, exif_data: Dict) -> Optional[str]:
        """Extrae el software usado para crear la imagen."""
        if 'Image Software' in exif_data:
            return exif_data['Image Software']
        return None

    def _analyze_image_content(self, image_data: bytes) -> Dict:
        """
        Analiza el contenido de la imagen para detectar patrones interesantes.
        """
        analysis = {
            'image_type': None,
            'color_profile': None,
            'possible_sensitive_data': False,
            'patterns': []
        }

        try:
            # Determinar tipo de imagen
            if image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                analysis['image_type'] = 'PNG'
            elif image_data.startswith(b'\xff\xd8\xff'):
                analysis['image_type'] = 'JPEG'
            elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
                analysis['image_type'] = 'GIF'
            else:
                analysis['image_type'] = 'Unknown'

            # Buscar patrones sensibles en el contenido (sin analizar el contenido real)
            # Esto es solo un placeholder - en un entorno real usaríamos técnicas más avanzadas
            if 'password' in image_data.lower() or 'secret' in image_data.lower():
                analysis['possible_sensitive_data'] = True

            # Buscar patrones comunes en metadatos
            if 'EXIF Make' in analysis['metadata']['exif'] and 'Canon' in analysis['metadata']['exif']['EXIF Make']:
                analysis['patterns'].append('camera_canon')

            if 'EXIF Model' in analysis['metadata']['exif'] and 'iPhone' in analysis['metadata']['exif']['EXIF Model']:
                analysis['patterns'].append('iphone_camera')

        except Exception as e:
            logger.error(f"❌ Error al analizar contenido de imagen: {e}")

        return analysis

    def execute(self, input_data: Dict) -> Dict:
        """
        Ejecuta el nodo con los datos de entrada proporcionados.
        """
        if not self.validate_input(input_data):
            return {
                'node_id': self.node_id,
                'status': 'input_validation_failed',
                'error': 'Datos de entrada inválidos',
                'timestamp': datetime.now().isoformat()
            }

        self.status = "active"
        target = input_data['target']
        max_images = input_data.get('max_images', DEFAULT_MAX_IMAGES)
        depth = input_data.get('depth', DEFAULT_DEPTH)
        search_engines = input_data.get('search_engines', DEFAULT_SEARCH_ENGINES)

        logger.info(f"🔍 Iniciando búsqueda de imágenes para término: {target}")

        result = {
            'target': target,
            'status': 'processing',
            'images_found': 0,
            'images_analyzed': 0,
            'metadata_extracted': [],
            'sources': {},
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'platform': platform.system(),
                'python_version': platform.python_version(),
                'max_images': max_images,
                'search_engines': search_engines
            }
        }

        # Realizar búsquedas de imágenes
        image_urls = self._search_images(target, search_engines)

        if not image_urls:
            result['status'] = 'no_images_found'
            return {
                **result,
                'node_id': self.node_id,
                'version': self.version
            }

        result['images_found'] = len(image_urls)
        logger.info(f"📷 Encontradas {len(image_urls)} imágenes potenciales")

        # Procesar imágenes (hasta el límite máximo)
        for i, url in enumerate(image_urls[:max_images]):
            try:
                logger.info(f"📥 Procesando imagen {i+1}/{min(len(image_urls), max_images)}: {url}")

                # Descargar imagen
                image_data = self._download_image(url)
                if not image_data:
                    continue

                # Extraer metadatos
                metadata = self._extract_metadata(image_data)

                # Analizar contenido
                analysis = self._analyze_image_content(image_data)
                metadata['analysis'] = analysis

                # Guardar resultados
                result['metadata_extracted'].append({
                    'url': url,
                    'metadata': metadata,
                    'source': urlparse(url).netloc,
                    'analysis': analysis
                })

                # Registrar fuente
                source_domain = urlparse(url).netloc
                if source_domain not in result['sources']:
                    result['sources'][source_domain] = 0
                result['sources'][source_domain] += 1

                result['images_analyzed'] += 1

                # Detener si se alcanzó el límite
                if result['images_analyzed'] >= max_images:
                    break

            except Exception as e:
                logger.error(f"❌ Error al procesar imagen {url}: {e}")
                continue

        # Actualizar estado final
        result['status'] = 'completed'
        result['node_id'] = self.node_id
        result['version'] = self.version

        self.status = "inactive"
        return result

    def get_info(self) -> Dict:
        """Devuelve información del nodo."""
        return {
            'node_id': self.node_id,
            'version': self.version,
            'status': self.status,
            'description': 'Rastreador sigiloso de metadatos de imágenes públicas',
            'input_interface': {
                'target': 'Término de búsqueda, nombre o URL para localizar imágenes',
                'search_engines': 'Lista de motores de búsqueda a usar (opcional)',
                'max_images': 'Número máximo de imágenes a analizar (opcional)',
                'depth': 'Profundidad de búsqueda (opcional)'
            },
            'output_interface': {
                'target': 'Término de búsqueda original',
                'status': 'Estado del proceso',
                'images_found': 'Número total de imágenes encontradas',
                'images_analyzed': 'Número de imágenes analizadas',
                'metadata_extracted': 'Lista de metadatos extraídos de cada imagen',
                'sources': 'Diccionario de dominios fuentes y conteo de imágenes',
                'timestamp': 'Fecha y hora de ejecución',
                'metadata': 'Información adicional del sistema'
            }
        }

# Ejemplo de uso
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=f"{NODE_ID} - Rastreador sigiloso de metadatos de imágenes")
    parser.add_argument("target", help="Término de búsqueda, nombre o URL")
    parser.add_argument("--max-images", type=int, default=DEFAULT_MAX_IMAGES, help="Número máximo de imágenes a analizar")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="Profundidad de búsqueda")
    args = parser.parse_args()

    node = NOD_PHANTOM_OSINT()

    input_data = {
        'target': args.target,
        'max_images': args.max_images,
        'depth': args.depth
    }

    result = node.execute(input_data)

    print(json.dumps(result, indent=2))