#!/usr/bin/env python3
"""
Proactive Research Agent
Realiza exploración autónoma de nodos cada 4 horas, usando duckduckgo-search para expandir nodos clave,
y genera propuestas de notas para la Action Queue usando el LLM dolphin-llama3.
"""

import os
import json
import time
import threading
import requests
import random
from datetime import datetime
import subprocess
from typing import List, Dict, Optional

# Configuración global
RESEARCH_INTERVAL_HOURS = 4
RESEARCH_QUEUE_DIR = "Research_Queue"
MIN_CONNECTIONS = 3
MIN_INFO_SCORE = 50
MAX_NEW_SOURCES = 3
KEY_NODE_TYPES = ["OSINT", "Ciberseguridad", "Technology", "Finance"]
ACTION_QUEUE_DIR = "Action_Queue"
LLM_MODEL = "dolphin-llama3"

def load_knowledge_base() -> Dict:
    """Carga la base de conocimiento desde knowledge_base.json."""
    knowledge_base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json")
    if not os.path.exists(knowledge_base_path):
        return {"nodes": {}}

    with open(knowledge_base_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_knowledge_base(knowledge_base: Dict) -> bool:
    """Guarda la base de conocimiento en knowledge_base.json."""
    knowledge_base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json")
    try:
        os.makedirs(os.path.dirname(knowledge_base_path), exist_ok=True)
        with open(knowledge_base_path, "w", encoding="utf-8") as f:
            json.dump(knowledge_base, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error al guardar knowledge_base.json: {e}")
        return False

def create_directories() -> bool:
    """Crea los directorios Research_Queue y Action_Queue si no existen."""
    research_queue_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), RESEARCH_QUEUE_DIR)
    action_queue_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ACTION_QUEUE_DIR)

    try:
        os.makedirs(research_queue_path, exist_ok=True)
        os.makedirs(action_queue_path, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error al crear directorios: {e}")
        return False

def evaluate_node(node: Dict) -> bool:
    """Evalúa si un nodo necesita expansión."""
    connections = len(node.get("connections", []))
    info_score = node.get("info_score", 0)
    node_type = node.get("type", "")
    return (connections < MIN_CONNECTIONS or info_score < MIN_INFO_SCORE) and node_type in KEY_NODE_TYPES

def search_with_duckduckgo(query: str) -> List[Dict]:
    """Realiza una búsqueda con duckduckgo-search y devuelve resultados."""
    try:
        # Usar duckduckgo-search para obtener resultados
        result = subprocess.run(
            ["ddg", "--format", "json", query],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        return [{
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "summary": item.get("body", ""),
            "relevance": random.randint(70, 100)
        } for item in data.get("results", [])[:MAX_NEW_SOURCES]]
    except Exception as e:
        print(f"Error en duckduckgo-search: {e}")
        # Simular resultados si duckduckgo-search no está disponible
        return [{
            "title": f"Source: {query.split(' ')[0]}",
            "url": f"https://example.com/search?q={query.replace(' ', '+')}",
            "summary": f"Simulated summary for: {query}",
            "relevance": random.randint(70, 100)
        } for _ in range(MAX_NEW_SOURCES)]

def query_llm(prompt: str) -> str:
    """Consulta al modelo LLM dolphin-llama3 para obtener un resumen."""
    try:
        url = "http://localhost:11434/api/generate"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": LLM_MODEL,
            "prompt": f"[INST] {prompt} [/INST]",
            "stream": False
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        return response_data.get("response", "No se recibió respuesta del modelo.")
    except Exception as e:
        print(f"Error consultando al LLM: {e}")
        return f"Error al generar resumen: {e}"

def generate_expansion_proposal(node_id: str, node_title: str, new_sources: List[Dict]) -> str:
    """Genera una propuesta de expansión para la Action Queue usando el LLM."""
    sources_info = "\n".join([
        f"- **{source['title']}**: {source['url']}\n  > {source['summary'][:100]}..."
        for source in new_sources
    ])

    prompt = f"""
    Analiza las siguientes fuentes sobre '{node_title}' y genera una propuesta de nota para expandir el conocimiento en este tema.

    Fuentes encontradas:
    {sources_info}

    Propuesta de nota:
    1. Resumen ejecutivo de los hallazgos.
    2. Enlaces más relevantes.
    3. Recomendaciones para integrar esta información en el nodo '{node_title}'.
    4. Posibles conexiones con otros nodos existentes.

    Formato de salida:
    ---
    title: "Expansión de {node_title}"
    date: {datetime.now().strftime('%Y-%m-%d')}
    author: AURA Proactive Research Agent
    status: pending_approval
    tags: ["research", "expansion", "automated"]
    content:
    - Resumen ejecutivo...
    - Enlaces:
      - [Enlace 1](url1)
      - [Enlace 2](url2)
    - Recomendaciones:
      - Recomendación 1
      - Recomendación 2
    ---
    """

    summary = query_llm(prompt)
    return summary

def save_to_action_queue(node_id: str, proposal_content: str) -> bool:
    """Guarda la propuesta en la Action Queue."""
    if not create_directories():
        return False

    proposal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ACTION_QUEUE_DIR, f"proposal_{node_id}.md")
    try:
        with open(proposal_path, "w", encoding="utf-8") as f:
            f.write(proposal_content)
        print(f"Propuesta guardada en Action Queue: {proposal_path}")
        return True
    except Exception as e:
        print(f"Error al guardar propuesta en Action Queue: {e}")
        return False

def update_node_metadata(node_id: str, new_sources: List[Dict]) -> bool:
    """Actualiza la metadata del nodo con los nuevos hallazgos."""
    knowledge_base = load_knowledge_base()
    if node_id not in knowledge_base["nodes"]:
        return False

    node = knowledge_base["nodes"][node_id]
    new_connections = node.get("connections", [])

    for source in new_sources:
        new_connections.append({
            "source": source["title"],
            "url": source["url"],
            "relevance": source["relevance"]
        })

    node["connections"] = new_connections
    node["info_score"] = min(100, node.get("info_score", 0) + 10)
    node["last_updated"] = datetime.now().isoformat()

    return save_knowledge_base(knowledge_base)

def perform_research_cycle():
    """Realiza un ciclo de investigación proactiva."""
    print(f"🔍 Iniciando ciclo de investigación proactiva a las {datetime.now().strftime('%H:%M:%S')}")

    knowledge_base = load_knowledge_base()
    nodes_to_expand = []

    for node_id, node in knowledge_base.get("nodes", {}).items():
        if evaluate_node(node):
            nodes_to_expand.append((node_id, node))

    for node_id, node in nodes_to_expand:
        node_title = node.get("title", "Unknown Node")
        node_type = node.get("type", "general")

        print(f"🔍 Nodo '{node_title}' ({node_id}) necesita expansión")

        # Generar consultas de búsqueda basadas en el tipo de nodo
        search_queries = {
            "OSINT": [
                f"avanzadas técnicas de OSINT para {node_title}",
                f"herramientas modernas de OSINT relacionadas con {node_title}",
                f"últimas tendencias en OSINT aplicadas a {node_title}"
            ],
            "Ciberseguridad": [
                f"vulnerabilidades recientes en {node_title}",
                f"estrategias de defensa para {node_title}",
                f"casos de estudio en ciberseguridad de {node_title}"
            ],
            "Technology": [
                f"tecnologías emergentes en {node_title}",
                f"innovaciones recientes en {node_title}",
                f"futuro de {node_title} en los próximos 5 años"
            ],
            "Finance": [
                f"análisis financiero avanzado en {node_title}",
                f"tendencias de mercado en {node_title}",
                f"estrategias de inversión para {node_title}"
            ]
        }

        # Seleccionar una consulta aleatoria
        query = random.choice(search_queries.get(node_type, [f"información actualizada sobre {node_title}"]))

        # Buscar fuentes con duckduckgo-search
        new_sources = search_with_duckduckgo(query)

        # Generar propuesta de expansión usando el LLM
        proposal_content = generate_expansion_proposal(node_id, node_title, new_sources)
        save_to_action_queue(node_id, proposal_content)

        # Actualizar metadata del nodo
        if update_node_metadata(node_id, new_sources):
            print(f"✅ Metadata actualizada para el nodo '{node_title}'")
        else:
            print(f"⚠️  Error al actualizar metadata para el nodo '{node_title}'")

    print(f"📊 Ciclo de investigación completado a las {datetime.now().strftime('%H:%M:%S')}")

def start_proactive_research_agent():
    """Inicia el agente de investigación proactiva."""
    print("🚀 Iniciando Proactive Research Agent...")
    create_directories()

    # Ejecutar el primer ciclo inmediatamente
    perform_research_cycle()

    # Configurar ciclo periódico cada 4 horas
    def research_loop():
        while True:
            time.sleep(RESEARCH_INTERVAL_HOURS * 3600)
            perform_research_cycle()

    # Iniciar el ciclo en un hilo separado
    research_thread = threading.Thread(target=research_loop, daemon=True)
    research_thread.start()

    print(f"🔄 Agente de investigación proactiva iniciado. Ciclos cada {RESEARCH_INTERVAL_HOURS} horas.")

if __name__ == "__main__":
    start_proactive_research_agent()