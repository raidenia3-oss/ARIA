#!/usr/bin/env python3
"""
Servidor AME con integración GBrain - Motor de conocimiento híbrido Obsidian+GBrain
Este servidor actúa como proxy des-censor y orquestador central para el ecosistema AURA/AME,
incorporando búsqueda semántica y relacional sobre la bóveda de conocimiento.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime
import requests
from flask import Flask, request, jsonify
import sys
import importlib.util

# Determinar la raíz del proyecto (directorio donde está el script servidor_gbrain.py)
SCRIPT_DIR = Path(__file__).resolve().parent.parent  # Subir de AME-termux a la raíz del proyecto
VAULT_PATH = SCRIPT_DIR / "AME_EXPORT_PACKAGE" / "AURA_INTELLIGENCE_VAULT"
GBRAIN_MODULE_DIR = SCRIPT_DIR / "AME_EXPORT_PACKAGE"

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AME_Server')

# Configuración de modelos LLM
MODELOS = [
    {
        "nombre": "Mistral",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "key": os.getenv("MISTRAL_API_KEY"),
        "modelo": "codestral-latest"
    },
    {
        "nombre": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key": os.getenv("CEREBRAS_API_KEY"),
        "modelo": "llama-3.3-70b"
    },
    {
        "nombre": "DeepSeek",
        "url": "https://api.deepseek.com/chat/completions",
        "key": os.getenv("DEEPSEEK_API_KEY"),
        "modelo": "deepseek-chat"
    }
]

# Inicializar Flask
app = Flask(__name__)

# Configuración de GBrain
class GBrainIntegration:
    """
    Clase para manejar la integración con el motor GBrain.
    """

    def __init__(self, vault_path: Optional[str] = None):
        """
        Inicializa la integración con GBrain.

        Args:
            vault_path: Ruta a la bóveda de conocimiento
        """
        self.vault_path = Path(vault_path) if vault_path else VAULT_PATH
        self.gbrain_initialized = False
        self.orchestrator = None
        self.utils = None
        self._initialize_gbrain()

    def _initialize_gbrain(self):
        """Inicializa el motor GBrain."""
        try:
            # Añadir el directorio de módulos GBrain al sys.path usando rutas absolutas
            gbrain_core_dir = GBRAIN_MODULE_DIR / "TERMUX_AGENT" / "core"
            gbrain_scripts_dir = GBRAIN_MODULE_DIR / "scripts"
            
            sys.path.insert(0, str(GBRAIN_MODULE_DIR))
            sys.path.insert(0, str(gbrain_core_dir))
            sys.path.insert(0, str(gbrain_scripts_dir))

            # Importar el orquestador
            try:
                from gbrain_orchestrator import GBrainOrchestrator
                self.orchestrator = GBrainOrchestrator(str(self.vault_path))
                self.gbrain_initialized = True
                
                # Importar las utilidades
                try:
                    from gbrain_utils import GBrainUtils
                    self.utils = GBrainUtils(str(self.vault_path))
                except Exception as e:
                    logger.warning(f"No se pudieron cargar las utilidades de GBrain: {str(e)}")

            except Exception as e:
                logger.error(f"No se pudo inicializar GBrain: {str(e)}")
                self.gbrain_initialized = False

        except Exception as e:
            logger.error(f"Error al inicializar integración GBrain: {str(e)}")
            self.gbrain_initialized = False

    def search_knowledge(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Realiza una búsqueda semántica en la bóveda de conocimiento.

        Args:
            query: Consulta de búsqueda
            top_k: Número de resultados a devolver

        Returns:
            Lista de resultados ordenados por relevancia
        """
        if not self.gbrain_initialized or not self.orchestrator:
            return []

        try:
            return self.orchestrator.search(query, top_k)
        except Exception as e:
            logger.error(f"Error al buscar conocimiento: {str(e)}")
            return []

    def get_related_files(self, file_id: str, top_k: int = 3) -> List[Dict]:
        """
        Obtiene archivos relacionados con un archivo específico basado en el grafo.

        Args:
            file_id: ID del archivo de referencia
            top_k: Número de archivos relacionados a devolver

        Returns:
            Lista de archivos relacionados ordenados por relevancia
        """
        if not self.gbrain_initialized or not self.orchestrator:
            return []

        try:
            return self.orchestrator.get_related_files(file_id, top_k)
        except Exception as e:
            logger.error(f"Error al obtener archivos relacionados: {str(e)}")
            return []

    def generate_context(self, query: str, top_k: int = 3) -> Dict:
        """
        Genera contexto relevante a partir de una consulta usando el grafo de conocimiento.

        Args:
            query: Consulta de búsqueda
            top_k: Número de archivos relacionados a incluir

        Returns:
            Diccionario con contexto relevante
        """
        if not self.gbrain_initialized or not self.utils:
            return {
                'query': query,
                'results': [],
                'related_files': [],
                'summary': '',
                'key_phrases': [],
                'graph_analysis': {}
            }

        try:
            return self.utils.generate_context_from_query(query, top_k)
        except Exception as e:
            logger.error(f"Error al generar contexto: {str(e)}")
            return {
                'query': query,
                'error': f"Error al generar contexto: {str(e)}"
            }

    def get_knowledge_status(self) -> Dict:
        """
        Obtiene el estado actual del conocimiento.

        Returns:
            Diccionario con el estado del conocimiento
        """
        if not self.gbrain_initialized or not self.orchestrator:
            return {
                'status': 'error',
                'message': 'GBrain no está inicializado',
                'files_processed': 0,
                'nodes_in_graph': 0,
                'edges_in_graph': 0
            }

        try:
            return {
                'status': 'active',
                'files_processed': len(self.orchestrator.file_index),
                'nodes_in_graph': self.orchestrator.graph.number_of_nodes(),
                'edges_in_graph': self.orchestrator.graph.number_of_edges(),
                'last_sync': self._get_last_sync_time(),
                'vault_size_mb': self._get_vault_size_mb()
            }
        except Exception as e:
            logger.error(f"Error al obtener estado del conocimiento: {str(e)}")
            return {
                'status': 'error',
                'message': f"Error al obtener estado: {str(e)}"
            }

    def _get_last_sync_time(self) -> Optional[str]:
        """Obtiene la fecha de la última sincronización."""
        if not self.gbrain_initialized or not self.orchestrator or not hasattr(self.orchestrator, 'index_path'):
            return None

        try:
            if not self.orchestrator.index_path.exists():
                return None

            stat = self.orchestrator.index_path.stat()
            return datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception:
            return None

    def _get_vault_size_mb(self) -> float:
        """Obtiene el tamaño aproximado de la bóveda en MB."""
        if not self.gbrain_initialized or not self.orchestrator:
            return 0.0

        try:
            total_size = 0
            for root, _, files in os.walk(self.vault_path):
                for file in files:
                    if file.endswith(('.md', '.db', '.json')):
                        file_path = Path(root) / file
                        total_size += file_path.stat().st_size

            return total_size / (1024 * 1024)  # Convertir a MB
        except Exception:
            return 0.0

# Inicializar integración GBrain
gbrain_integration = GBrainIntegration()

@app.route('/v1/chat/completions', methods=['POST'])
def completions():
    """
    Endpoint principal para completaciones de chat con integración GBrain.
    """
    data = request.json
    mensajes = data.get("messages", [])

    # Obtener el contexto de la consulta usando GBrain
    query = mensajes[-1].get("content", "") if mensajes else ""
    context = gbrain_integration.generate_context(query) if query else {}

    # Si hay contexto relevante, añadirlo a los mensajes
    if context and context.get('summary'):
        # Formatear el contexto como un mensaje de sistema
        context_message = {
            "role": "system",
            "content": f"""
            Contexto relevante de la bóveda de conocimiento AURA/AME:
            {context['summary']}

            Archivos relacionados:
            {', '.join([f"{rel['title']} ({rel['path']})" for rel in context.get('related_files', [])])}

            Frases clave: {', '.join(context.get('key_phrases', []))}
            """
        }

        # Insertar el contexto como el primer mensaje
        mensajes.insert(0, context_message)

    # Procesar con los modelos LLM
    for modelo in MODELOS:
        try:
            logger.info(f"[AME] Intentando: {modelo['nombre']}")
            headers = {
                "Authorization": f"Bearer {modelo['key']}",
                "Content-Type": "application/json"
            }
            body = {
                "model": modelo["modelo"],
                "messages": mensajes,
                "max_tokens": data.get("max_tokens", 4096),
                "temperature": data.get("temperature", 0.7)
            }
            r = requests.post(modelo["url"], headers=headers, json=body, timeout=30)

            if r.status_code == 200:
                logger.info(f"[AME] OK con {modelo['nombre']}")
                return jsonify(r.json())
            elif r.status_code == 429:
                logger.info(f"[AME] {modelo['nombre']} saturado, cambiando...")
                time.sleep(2)
                continue
            else:
                logger.error(f"[AME] {modelo['nombre']} error {r.status_code}")
                continue
        except Exception as e:
            logger.error(f"[AME] {modelo['nombre']} fallo: {e}")
            continue

    return jsonify({"error": "Todos los modelos fallaron"}), 500

@app.route('/v1/knowledge/search', methods=['POST'])
def knowledge_search():
    """
    Endpoint para búsqueda semántica en la bóveda de conocimiento.
    """
    data = request.json
    query = data.get("query", "")
    top_k = data.get("top_k", 5)

    if not query:
        return jsonify({"error": "Consulta de búsqueda vacía"}), 400

    try:
        results = gbrain_integration.search_knowledge(query, top_k)

        # Formatear resultados para respuesta API
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.get("id"),
                "file_id": result.get("file_id"),
                "chunk_id": result.get("chunk_id"),
                "title": result.get("title"),
                "path": result.get("path"),
                "content": result.get("content", "")[:500] + ("..." if len(result.get("content", "")) > 500 else ""),
                "similarity": result.get("similarity", 0.0),
                "metadata": result.get("metadata", {})
            })

        return jsonify({
            "query": query,
            "results": formatted_results,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error al buscar conocimiento: {str(e)}")
        return jsonify({"error": f"Error al buscar conocimiento: {str(e)}"}), 500

@app.route('/v1/knowledge/context', methods=['POST'])
def knowledge_context():
    """
    Endpoint para generar contexto relevante a partir de una consulta.
    """
    data = request.json
    query = data.get("query", "")
    top_k = data.get("top_k", 3)

    if not query:
        return jsonify({"error": "Consulta de contexto vacía"}), 400

    try:
        context = gbrain_integration.generate_context(query, top_k)

        # Formatear resultados para respuesta API
        formatted_results = []
        for result in context.get("results", []):
            formatted_results.append({
                "id": result.get("id"),
                "file_id": result.get("file_id"),
                "chunk_id": result.get("chunk_id"),
                "title": result.get("title"),
                "path": result.get("path"),
                "content": result.get("content", "")[:500] + ("..." if len(result.get("content", "")) > 500 else ""),
                "similarity": result.get("similarity", 0.0)
            })

        return jsonify({
            "query": query,
            "summary": context.get("summary", ""),
            "key_phrases": context.get("key_phrases", []),
            "related_files": [
                {
                    "file_id": rel.get("file_id"),
                    "title": rel.get("title"),
                    "path": rel.get("path"),
                    "weight": rel.get("weight", 0.0),
                    "relationship_type": rel.get("relationship_type", "")
                }
                for rel in context.get("related_files", [])
            ],
            "results": formatted_results,
            "graph_analysis": context.get("graph_analysis", {}),
            "status": "success",
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error al generar contexto: {str(e)}")
        return jsonify({"error": f"Error al generar contexto: {str(e)}"}), 500

@app.route('/v1/knowledge/status', methods=['GET'])
def knowledge_status():
    """
    Endpoint para obtener el estado del conocimiento.
    """
    try:
        status = gbrain_integration.get_knowledge_status()

        return jsonify({
            "status": status.get("status"),
            "message": status.get("message", ""),
            "files_processed": status.get("files_processed", 0),
            "nodes_in_graph": status.get("nodes_in_graph", 0),
            "edges_in_graph": status.get("edges_in_graph", 0),
            "last_sync": status.get("last_sync"),
            "vault_size_mb": status.get("vault_size_mb", 0.0),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error al obtener estado del conocimiento: {str(e)}")
        return jsonify({"error": f"Error al obtener estado: {str(e)}"}), 500

@app.route('/v1/models', methods=['GET'])
def models():
    """
    Endpoint para listar modelos disponibles (con integración GBrain).
    """
    return jsonify({
        "data": [
            {"id": "ame-router", "object": "model"},
            {"id": "gbrain-knowledge", "object": "knowledge_base"}
        ],
        "knowledge_status": gbrain_integration.get_knowledge_status()
    })

@app.route('/health', methods=['GET'])
def health():
    """
    Endpoint de salud del servidor.
    """
    return jsonify({
        "status": "healthy",
        "gbrain_integration": "active" if gbrain_integration.gbrain_initialized else "inactive",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    # Verificar que la bóveda exista
    if not gbrain_integration.vault_path.exists():
        logger.error(f"La bóveda de conocimiento no existe en: {gbrain_integration.vault_path}")
        logger.info("Creando estructura de bóveda...")
        try:
            gbrain_integration.vault_path.mkdir(parents=True, exist_ok=True)
            logger.info("Estructura de bóveda creada. Iniciando servidor...")
        except Exception as e:
            logger.error(f"Error al crear estructura de bóveda: {str(e)}")
            sys.exit(1)
    else:
        logger.info("Bóveda de conocimiento encontrada. Iniciando servidor...")

    print("=== AME Servidor con integración GBrain activo en puerto 5000 ===")
    print(f"Ruta de la bóveda: {gbrain_integration.vault_path}")
    print(f"Estado de GBrain: {'ACTIVO' if gbrain_integration.gbrain_initialized else 'INACTIVO'}")

    # Iniciar servidor
    app.run(host="0.0.0.0", port=5000)