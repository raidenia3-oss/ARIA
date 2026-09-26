#!/usr/bin/env python3
"""
Deep Knowledge RAG para AURA.
Indexa archivos locales (.md, logs, scripts) en ChromaDB y permite recuperación semántica de conocimiento.
"""

import os
import json
import time
import uuid
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings
from datetime import datetime
import subprocess
import re
from flask import Flask, request, jsonify
import requests
import threading

app = Flask(__name__)

# Configuración global
CHROMA_DB_DIR = "chroma_db_knowledge"
CHROMA_COLLECTION_NAME = "aura_knowledge_collection"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Modelo de embedding ligero
INDEXING_INTERVAL = 3600  # 1 hora entre indexaciones automáticas
MAX_DOCUMENTS = 1000  # Máximo de documentos en la colección

# Inicializar ChromaDB
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

# Crear o obtener colección
try:
    collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}
    )
except Exception as e:
    print(f"Error al crear colección ChromaDB: {e}")
    collection = None

# Configuración de archivos a indexar
FILE_TYPES = {
    "markdown": [".md", ".markdown"],
    "logs": [".log", ".txt"],
    "scripts": [".py", ".sh", ".js", ".java", ".c", ".cpp", ".go", ".rs"]
}

# Directorio base para buscar archivos
BASE_DIRS = [
    os.getcwd(),
    os.path.join(os.getcwd(), "AURA_Core"),
    os.path.join(os.getcwd(), "Shadow-Core"),
    os.path.join(os.getcwd(), "AME_Core"),
    os.path.join(os.getcwd(), "_AURA_Archive")
]

# Estado de indexación
INDEXING_STATUS = {
    "last_indexed": None,
    "total_documents": 0,
    "last_error": None
}

def load_knowledge_config():
    """Cargar configuración de conocimiento desde archivo."""
    config_path = os.path.join(os.getcwd(), "AURA_Core", "knowledge_config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {
        "file_types": FILE_TYPES,
        "base_dirs": BASE_DIRS,
        "embedding_model": EMBEDDING_MODEL,
        "max_documents": MAX_DOCUMENTS
    }

def save_knowledge_config(config):
    """Guardar configuración de conocimiento en archivo."""
    config_path = os.path.join(os.getcwd(), "AURA_Core", "knowledge_config.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

def find_files_to_index():
    """Encontrar archivos que necesitan ser indexados."""
    indexed_files = set()
    if collection:
        for doc in collection.get()["ids"]:
            metadata = collection.get(ids=[doc])["metadatas"][0]
            indexed_files.add(metadata.get("file_path", ""))

    files_to_index = []
    for root_dir in BASE_DIRS:
        if not os.path.exists(root_dir):
            continue

        for root, _, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()

                # Verificar si el archivo debe ser indexado
                should_index = False
                for file_type, extensions in FILE_TYPES.items():
                    if file_ext in extensions:
                        should_index = True
                        break

                if should_index and file_path not in indexed_files:
                    files_to_index.append(file_path)

    return files_to_index

def extract_text_from_file(file_path):
    """Extraer texto de un archivo."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Procesar contenido según el tipo de archivo
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in [".md", ".markdown"]:
            # Procesar Markdown: extraer títulos y contenido principal
            lines = content.split('\n')
            processed_lines = []
            in_code_block = False
            for line in lines:
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue
                if not in_code_block:
                    processed_lines.append(line)

            content = '\n'.join(processed_lines)

        elif file_ext in [".log", ".txt"]:
            # Procesar logs: mantener solo líneas relevantes
            lines = content.split('\n')
            processed_lines = []
            for line in lines:
                if line.strip() and not line.strip().startswith(('INFO:', 'DEBUG:', 'TRACE:')):
                    processed_lines.append(line)

            content = '\n'.join(processed_lines)

        return content
    except Exception as e:
        print(f"Error al leer archivo {file_path}: {e}")
        return None

def index_file(file_path):
    """Indexar un archivo específico en ChromaDB."""
    if not collection:
        return False

    try:
        # Extraer texto del archivo
        content = extract_text_from_file(file_path)
        if not content:
            return False

        # Generar metadatos
        metadata = {
            "file_path": file_path,
            "file_type": os.path.splitext(file_path)[1].lower(),
            "file_size": os.path.getsize(file_path),
            "last_modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
            "content_type": "text" if os.path.splitext(file_path)[1].lower() in [".md", ".txt", ".log"] else "code"
        }

        # Dividir contenido en chunks (para documentos largos)
        chunks = []
        if len(content) > 1000:  # Si el contenido es muy largo
            sentences = re.split(r'(?<=[.!?])\s+', content)
            for i in range(0, len(sentences), 5):  # Crear chunks de 5 sentencias
                chunk = ' '.join(sentences[i:i+5])
                if len(chunk.strip()) > 0:
                    chunks.append(chunk)
        else:
            chunks = [content]

        # Indexar cada chunk
        for i, chunk in enumerate(chunks):
            chunk_id = f"{os.path.basename(file_path)}_{i}"
            collection.add(
                documents=[chunk],
                metadatas=[metadata],
                ids=[chunk_id]
            )

        print(f"✅ Indexado archivo: {file_path}")
        return True
    except Exception as e:
        print(f"❌ Error al indexar archivo {file_path}: {e}")
        return False

def index_files(files_to_index):
    """Indexar una lista de archivos."""
    if not collection:
        return False

    try:
        success_count = 0
        for file_path in files_to_index:
            if index_file(file_path):
                success_count += 1

        INDEXING_STATUS["last_indexed"] = datetime.now().isoformat()
        INDEXING_STATUS["total_documents"] = len(collection.get()["ids"])
        INDEXING_STATUS["last_error"] = None

        print(f"📚 Indexación completada: {success_count}/{len(files_to_index)} archivos indexados")
        return True
    except Exception as e:
        INDEXING_STATUS["last_error"] = str(e)
        print(f"❌ Error durante la indexación: {e}")
        return False

def perform_knowledge_retrieval(query, top_k=3):
    """Realizar recuperación de conocimiento usando ChromaDB."""
    if not collection:
        return {"status": "error", "message": "ChromaDB no está disponible"}

    try:
        # Realizar búsqueda semántica
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )

        # Procesar resultados
        context_chunks = []
        for i, (doc, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
            if doc.strip():
                context_chunks.append({
                    "source": metadata.get("file_path", "desconocido"),
                    "content": doc,
                    "relevance": 1 - results['distances'][i] if results['distances'] else 1.0
                })

        return {
            "status": "ok",
            "query": query,
            "results": context_chunks,
            "total_documents": len(collection.get()["ids"])
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al recuperar conocimiento: {str(e)}"
        }

def enhance_prompt_with_knowledge(prompt, system_prompt=None):
    """Enriquecer un prompt con conocimiento relevante recuperado."""
    try:
        # Realizar recuperación de conocimiento
        knowledge_result = perform_knowledge_retrieval(prompt)

        if knowledge_result["status"] == "ok" and knowledge_result["results"]:
            # Construir contexto para el prompt
            context_lines = []
            for result in knowledge_result["results"]:
                if result["content"].strip():
                    context_lines.append(f"Contexto relevante de {result['source']}:")
                    context_lines.append(f"\"\"\"\n{result['content']}\n\"\"\"")
                    context_lines.append("")

            context = "\n\n".join(context_lines)

            # Crear prompt mejorado
            enhanced_prompt = f"""
            {system_prompt or ""}

            CONTEXTO RELEVANTE:
            {context}

            PREGUNTA:
            {prompt}
            """

            return {
                "status": "ok",
                "enhanced_prompt": enhanced_prompt,
                "knowledge_sources": [r["source"] for r in knowledge_result["results"] if r["content"].strip()]
            }
        else:
            return {
                "status": "ok",
                "enhanced_prompt": prompt,
                "knowledge_sources": []
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al enriquecer prompt: {str(e)}",
            "enhanced_prompt": prompt
        }

def index_new_file(file_path):
    """Indexar un nuevo archivo individualmente."""
    if not collection:
        return False

    try:
        return index_file(file_path)
    except Exception as e:
        print(f"Error al indexar archivo nuevo {file_path}: {e}")
        return False

def start_auto_indexing():
    """Iniciar proceso de indexación automática en segundo plano."""
    def indexing_loop():
        while True:
            try:
                print(f"🔍 Iniciando indexación automática...")
                files_to_index = find_files_to_index()
                if files_to_index:
                    print(f"📂 Encontrados {len(files_to_index)} archivos para indexar")
                    index_files(files_to_index)
                else:
                    print("✅ Todos los archivos están indexados")

                # Esperar hasta la próxima indexación
                time.sleep(INDEXING_INTERVAL)
            except Exception as e:
                print(f"❌ Error en el bucle de indexación: {e}")
                time.sleep(INDEXING_INTERVAL)

    # Iniciar hilo de indexación automática
    threading.Thread(target=indexing_loop, daemon=True).start()

def initialize_knowledge_base():
    """Inicializar la base de conocimiento."""
    global collection, INDEXING_STATUS

    try:
        # Verificar si ChromaDB está disponible
        if not chroma_client:
            raise Exception("ChromaDB no está disponible")

        # Obtener estado actual
        if collection:
            INDEXING_STATUS["total_documents"] = len(collection.get()["ids"])
            INDEXING_STATUS["last_indexed"] = datetime.now().isoformat()

        # Iniciar indexación automática
        start_auto_indexing()

        print("✅ Base de conocimiento inicializada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error al inicializar base de conocimiento: {e}")
        INDEXING_STATUS["last_error"] = str(e)
        return False

@app.route('/api/knowledge/index', methods=['POST'])
def trigger_indexing():
    """Endpoint para disparar indexación manual."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 401

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    try:
        files_to_index = find_files_to_index()
        if not files_to_index:
            return jsonify({"status": "ok", "message": "No hay archivos nuevos para indexar"})

        success = index_files(files_to_index)
        if success:
            return jsonify({
                "status": "ok",
                "message": f"Indexación completada: {len(files_to_index)} archivos procesados",
                "total_documents": INDEXING_STATUS["total_documents"]
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Error durante la indexación",
                "error": INDEXING_STATUS.get("last_error", "Error desconocido")
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al disparar indexación: {str(e)}"
        })

@app.route('/api/knowledge/query', methods=['POST'])
def query_knowledge():
    """Endpoint para realizar consultas de conocimiento."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'query' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y consulta requeridas"}), 400

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    query = data['query']
    top_k = data.get('top_k', 3)

    try:
        result = perform_knowledge_retrieval(query, top_k)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al consultar conocimiento: {str(e)}"
        })

@app.route('/api/knowledge/enhance', methods=['POST'])
def enhance_prompt():
    """Endpoint para enriquecer un prompt con conocimiento relevante."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y prompt requeridos"}), 400

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    prompt = data['prompt']
    system_prompt = data.get('system_prompt')

    try:
        result = enhance_prompt_with_knowledge(prompt, system_prompt)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al enriquecer prompt: {str(e)}",
            "enhanced_prompt": prompt
        })

@app.route('/api/knowledge/status', methods=['GET'])
def get_knowledge_status():
    """Endpoint para obtener el estado de la base de conocimiento."""
    return jsonify({
        "status": "ok",
        "last_indexed": INDEXING_STATUS.get("last_indexed"),
        "total_documents": INDEXING_STATUS.get("total_documents", 0),
        "last_error": INDEXING_STATUS.get("last_error")
    })

def index_successful_command(command_output, command_type="terminal_command"):
    """Indexar la salida exitosa de un comando."""
    if not collection:
        return False

    try:
        # Generar un ID único para este comando
        command_id = f"command_{uuid.uuid4().hex}"

        # Crear metadatos
        metadata = {
            "command_type": command_type,
            "timestamp": datetime.now().isoformat(),
            "source": "terminal_command"
        }

        # Indexar la salida del comando
        collection.add(
            documents=[command_output],
            metadatas=[metadata],
            ids=[command_id]
        )

        print(f"✅ Indexada salida de comando: {command_id}")
        return True
    except Exception as e:
        print(f"❌ Error al indexar salida de comando: {e}")
        return False

if __name__ == "__main__":
    # Inicializar base de conocimiento
    if not initialize_knowledge_base():
        print("⚠️ No se pudo inicializar la base de conocimiento. Continuando sin indexación...")

    # Iniciar el servidor
    app.run(host='0.0.0.0', port=5012, debug=False)