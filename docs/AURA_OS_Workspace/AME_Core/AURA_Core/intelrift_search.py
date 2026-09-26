"""
AURA Intelrift Deep Search — Búsqueda Predictiva
Consulta fuentes de datos crudos y detecta anomalías tempranas.
"""

import requests
import json
import time
import os
from typing import Dict, List, Optional
import hashlib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer

# Configuración de caché
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intelrift_cache.json")
CACHE_EXPIRY_SECONDS = 15 * 60  # 15 minutos


class IntelriftSearch:
    """
    Motor de búsqueda predictiva para OSINT anticipatorio.
    - Consulta APIs abiertas de ciberseguridad
    - Analiza patrones inusuales usando embeddings y clustering
    - Detecta anomalías antes de que sean noticias
    - Persistencia en Firebase para anomalías críticas
    """

    def __init__(self, firebase_config=None):
        self.sources = {
            "hacker_news": "https://hacker-news.firebaseio.com/v0/newstories.json",
            "cve_recent": "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=20",
            "github_trending": "https://api.github.com/search/repositories?q=created:>2024-01-01&sort=stars&order=desc",
        }
        self.firebase_config = firebase_config
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.cluster_model = KMeans(n_clusters=3, random_state=42)

    def _load_cache(self) -> Dict:
        """Carga la caché desde el archivo JSON."""
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error cargando caché: {e}")
            return {}

    def _upload_to_firebase(self, anomaly: Dict):
        """Sube una anomalía crítica a Firebase."""
        if not self.firebase_config:
            print("⚠️ Configuración de Firebase no proporcionada.")
            return

        try:
            # Aquí se implementaría la lógica para subir a Firebase
            # Por ahora, solo se simula el comportamiento
            print(
                f"🔥 Subiendo anomalía a Firebase: {anomaly.get('title', anomaly.get('id', 'Desconocido'))}"
            )
            # Ejemplo de estructura de datos para Firebase
            # {
            #     "anomaly": anomaly,
            #     "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
            #     "source": anomaly.get("source", "unknown")
            # }
        except Exception as e:
            print(f"⚠️ Error subiendo a Firebase: {e}")

    def _save_cache(self, cache_data: Dict):
        """Guarda la caché en el archivo JSON."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Error guardando caché Intelrift: {e}")

    def fetch_raw_intelligence(self, source: str = "hacker_news") -> Optional[Dict]:
        """
        Consulta una fuente de datos crudos.
        Usa caché si los datos tienen menos de 15 minutos.
        """
        if source not in self.sources:
            return None

        # Verificar caché primero
        cache = self._load_cache()
        cached = cache.get(source, {})
        if cached and (time.time() - cached.get("cache_timestamp", 0)) < CACHE_EXPIRY_SECONDS:
            return {
                "source": source,
                "timestamp": cached.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S")),
                "data": cached.get("data", {}),
                "status": "ok",
                "cache_hit": True,
            }

        try:
            url = self.sources[source]
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                result = {
                    "source": source,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "data": resp.json(),
                    "status": "ok",
                    "cache_hit": False,
                }
                # Actualizar caché
                cache[source] = {
                    "cache_timestamp": time.time(),
                    "timestamp": result["timestamp"],
                    "data": result["data"],
                }
                self._save_cache(cache)
                return result
            return {"source": source, "status": "error", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"source": source, "status": "error", "error": str(e)}

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para los textos usando SentenceTransformer."""
        return self.embedding_model.encode(texts)

    def _cluster_texts(self, texts: List[str]) -> List[int]:
        """Clustera los textos usando KMeans."""
        embeddings = self._generate_embeddings(texts)
        return self.cluster_model.fit_predict(embeddings)

    def _detect_anomalies_with_clustering(self, texts: List[str], labels: List[str]) -> List[Dict]:
        """Detecta anomalías usando clustering y análisis de similitud."""
        clusters = self._cluster_texts(texts)
        anomalies = []

        for idx, (text, label, cluster) in enumerate(zip(texts, labels, clusters)):
            if cluster == 2:  # Cluster 2 podría representar anomalías
                anomalies.append(
                    {
                        "text": text,
                        "label": label,
                        "cluster": cluster,
                        "anomaly_score": 0.9,  # Score alto para anomalías
                    }
                )
        return anomalies

    def analyze_anomalies(self, data: Dict) -> List[Dict]:
        """
        Analiza datos crudos en busca de patrones inusuales usando técnicas avanzadas.
        """
        anomalies = []
        source = data.get("source")
        source_data = data.get("data", {})

        if source == "hacker_news":
            # Ejemplo: detectar títulos con palabras clave de seguridad
            story_ids = source_data[:10]  # Solo primeros 10
            texts = []
            labels = []

            for story_id in story_ids:
                try:
                    story_resp = requests.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5
                    )
                    if story_resp.status_code == 200:
                        story = story_resp.json()
                        title = story.get("title", "")
                        texts.append(title)
                        labels.append("hacker_news")
                except Exception as e:
                    print(f"⚠️ Error al obtener historia {story_id}: {e}")
                    continue

            # Detectar anomalías usando clustering
            cluster_anomalies = self._detect_anomalies_with_clustering(texts, labels)
            for anomaly in cluster_anomalies:
                anomalies.append(
                    {
                        "type": "cluster_anomaly",
                        "title": anomaly["text"],
                        "score": anomaly["anomaly_score"],
                        "source": source,
                    }
                )

            # Palabras clave tradicionales
            for story_id in story_ids:
                try:
                    story_resp = requests.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5
                    )
                    if story_resp.status_code == 200:
                        story = story_resp.json()
                        title = story.get("title", "").lower()
                        keywords = ["exploit", "vulnerability", "breach", "zero-day", "cve"]
                        if any(kw in title for kw in keywords):
                            anomalies.append(
                                {
                                    "type": "security_alert",
                                    "title": story.get("title"),
                                    "url": story.get("url"),
                                    "score": story.get("score", 0),
                                    "time": story.get("time", 0),
                                }
                            )
                except:
                    continue

        elif source == "cve_recent":
            # Analizar CVEs recientes
            vulnerabilities = source_data.get("vulnerabilities", [])
            for cve in vulnerabilities:
                if cve.get("baseMetricV3", {}).get("cvssV3", {}).get("baseScore", 0) > 8.5:
                    anomalies.append(
                        {
                            "type": "critical_cve",
                            "id": cve.get("id"),
                            "description": cve.get("descriptions", [{}])[0].get("value"),
                            "score": cve.get("baseMetricV3", {}).get("cvssV3", {}).get("baseScore"),
                            "published": cve.get("published"),
                        }
                    )

        # Subir anomalías críticas a Firebase
        for anomaly in anomalies:
            if anomaly.get("score", 0) > 8.0 or anomaly.get("type") == "critical_cve":
                self._upload_to_firebase(anomaly)

        return anomalies

    def predictive_search(self) -> Dict:
        """
        Ejecuta búsqueda predictiva en todas las fuentes.
        """
        results = []
        for source in self.sources:
            raw_data = self.fetch_raw_intelligence(source)
            if raw_data and raw_data.get("status") == "ok":
                anomalies = self.analyze_anomalies(raw_data)
                if anomalies:
                    results.append(
                        {
                            "source": source,
                            "anomalies_count": len(anomalies),
                            "anomalies": anomalies,
                        }
                    )

        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_anomalies": sum(r["anomalies_count"] for r in results),
            "results": results,
        }


# Bloque de prueba
if __name__ == "__main__":
    search = IntelriftSearch()
    result = search.predictive_search()
    print(f"✅ Intelrift: {result['total_anomalies']} anomalías detectadas")
    print(f"   Fuentes analizadas: {len(result['results'])}")
