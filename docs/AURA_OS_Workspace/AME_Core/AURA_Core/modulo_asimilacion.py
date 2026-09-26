"""
AURA Stark Extraction Engine — Ingeniería Inversa Automatizada
Analiza recursos externos (URLs, archivos) y extrae lógica técnica aplicable.
"""
import os
import json
import requests
import base64
from typing import Dict, Optional
from datetime import datetime
from urllib.parse import urlparse

class StarkExtractionEngine:
    """
    Motor de asimilación de recursos externos.
    - Extrae texto, metadatos y lógica de URLs/archivos
    - Usa Mistral para ingeniería inversa
    - Genera código sugerido y vectores de inspiración
    """

    def __init__(self):
        self.inspiration_pool_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'knowledge_base',
            'inspiration_pool.json'
        )
        os.makedirs(os.path.dirname(self.inspiration_pool_path), exist_ok=True)

    def _load_inspiration_pool(self) -> Dict:
        """Carga el pool de inspiración existente."""
        if not os.path.exists(self.inspiration_pool_path):
            return {"inspirations": []}
        try:
            with open(self.inspiration_pool_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error cargando inspiration_pool: {e}")
            return {"inspirations": []}

    def _save_inspiration_pool(self, data: Dict):
        """Guarda el pool de inspiración."""
        try:
            with open(self.inspiration_pool_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Error guardando inspiration_pool: {e}")

    def _extract_text_from_url(self, url: str) -> Optional[str]:
        """Extrae texto de una URL (GitHub, tweets, artículos)."""
        try:
            headers = {
                'User-Agent': 'AURA-StarkEngine/1.0'
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.text[:5000]
            return None
        except Exception as e:
            print(f"⚠️  Error fetching URL: {e}")
            return None

    def _extract_text_from_file(self, file_path: str) -> Optional[str]:
        """Extrae texto de un archivo local."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()[:5000]
        except Exception as e:
            print(f"⚠️  Error reading file: {e}")
            return None

    def _analyze_with_mistral(self, text: str, source_type: str) -> Dict:
        """
        Simula análisis con Mistral (en producción usaría ai_router).
        Retorna estructura de ingeniería inversa.
        """
        result = {
            "funcionalidad_detectada": "",
            "componentes_requeridos": [],
            "codigo_sugerido": "",
            "vector_de_inspiracion": []
        }

        if "github" in source_type or "code" in text.lower():
            result["funcionalidad_detectada"] = "Repositorio de código con algoritmos de procesamiento de datos"
            result["componentes_requeridos"] = ["pandas", "numpy", "matplotlib"]
            result["codigo_sugerido"] = """# Ejemplo de código sugerido
import pandas as pd
def process_data(df):
    return df.cleaned()"""
            result["vector_de_inspiracion"] = [
                "Integrar con OSINT Radar para análisis en tiempo real",
                "Usar Three.js para visualización 3D de datos"
            ]

        elif "twitter" in source_type or "tweet" in text.lower():
            result["funcionalidad_detectada"] = "Sistema de monitoreo de redes sociales"
            result["componentes_requeridos"] = ["tweepy", "textblob", "sqlite3"]
            result["codigo_sugerido"] = """# Ejemplo de monitoreo
import tweepy
def monitor_tweets(query):
    auth = tweepy.OAuthHandler('API_KEY', 'API_SECRET')
    api = tweepy.API(auth)
    return api.search_tweets(q=query)"""
            result["vector_de_inspiracion"] = [
                "Combinar con CSI Radar para detección de amenazas",
                "Añadir análisis de sentimiento con Mistral"
            ]

        elif "image" in source_type or "jpg" in text.lower() or "png" in text.lower():
            result["funcionalidad_detectada"] = "Procesamiento de imágenes con visión por computadora"
            result["componentes_requeridos"] = ["opencv-python", "pillow", "tensorflow"]
            result["codigo_sugerido"] = """# Ejemplo de procesamiento
import cv2
def analyze_image(path):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)"""
            result["vector_de_inspiracion"] = [
                "Integrar con gestos de MediaPipe para interacción",
                "Usar en Antigravity Nodes para análisis visual"
            ]

        else:
            result["funcionalidad_detectada"] = "Recurso genérico con potencial de análisis"
            result["componentes_requeridos"] = ["requests", "beautifulsoup4"]
            result["codigo_sugerido"] = """# Ejemplo genérico
import requests
def fetch_data(url):
    resp = requests.get(url)
    return resp.json()"""
            result["vector_de_inspiracion"] = [
                "Conectar con Evolution Engine para optimización",
                "Almacenar en VOID para memoria persistente"
            ]

        return result

    def assimilar_recurso(self, source_type: str, data: str) -> Dict:
        """
        Procesa un recurso y extrae información técnica.

        Args:
            source_type: 'url', 'file', 'image', 'tweet', 'github'
            data: URL o path del archivo

        Returns:
            Dict con análisis estructurado
        """
        if source_type == 'url':
            text = self._extract_text_from_url(data)
        elif source_type == 'file':
            text = self._extract_text_from_file(data)
        else:
            text = data

        if not text:
            return {"error": "No se pudo extraer contenido"}

        analysis = self._analyze_with_mistral(text, source_type)

        inspiration = {
            "id": f"insp_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "source_type": source_type,
            "source_data": data[:100] + ("..." if len(data) > 100 else ""),
            "analysis": analysis
        }

        pool = self._load_inspiration_pool()
        pool["inspirations"].insert(0, inspiration)
        pool["inspirations"] = pool["inspirations"][:50]
        self._save_inspiration_pool(pool)

        return {
            "status": "ok",
            "inspiration_id": inspiration["id"],
            "analysis": analysis
        }


if __name__ == "__main__":
    engine = StarkExtractionEngine()
    result = engine.assimilar_recurso("url", "https://github.com/example/repo")
    print(f"✅ Asimilación completada: {result['inspiration_id']}")
    print(f"   Funcionalidad: {result['analysis']['funcionalidad_detectada']}")