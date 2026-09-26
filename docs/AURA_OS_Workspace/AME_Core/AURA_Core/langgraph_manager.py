#!/usr/bin/env python3
"""
LangGraph Manager para AURA.
Implementa ciclos de tareas: [Tarea -> Ejecución -> Verificación -> Re-intento si hay error].
"""

from langgraph.graph import Graph
from langgraph.prebuilt import ToolNode
from typing import Dict, Any
import time
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Definir herramientas disponibles
tools = {
    "osint_search": {
        "description": "Realiza búsquedas OSINT en la web.",
        "function": lambda query: self._perform_osint_search(query)
    },
    "file_analysis": {
        "description": "Analiza archivos locales.",
        "function": lambda file_path: self._analyze_file(file_path)
    },
    "database_query": {
        "description": "Consulta la base de datos de AURA.",
        "function": lambda query: self._query_database(query)
    }
}

class LangGraphManager:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self) -> Graph:
        """
        Construye el grafo LangGraph para manejar tareas.
        """
        workflow = Graph()

        # Nodos de herramientas
        osint_node = ToolNode(tools["osint_search"])
        analysis_node = ToolNode(tools["file_analysis"])
        db_node = ToolNode(tools["database_query"])

        # Nodo de verificación
        def verify_task(task_result):
            """
            Verifica si la tarea se ejecutó correctamente.
            """
            if "error" in task_result:
                print(f"⚠️ Error en la tarea: {task_result['error']}")
                return {"status": "failed", "task_result": task_result}
            else:
                print("✅ Tarea ejecutada correctamente.")
                return {"status": "success", "task_result": task_result}

        verify_node = workflow.add_node(verify_task)

        # Nodo de reintento
        def retry_task(task):
            """
            Intenta reejecutar la tarea si falló.
            """
            print("🔄 Reintentando tarea...")
            time.sleep(2)  # Esperar antes de reintentar
            return self._execute_task(task)

        retry_node = workflow.add_node(retry_task)

        # Definir el flujo de trabajo
        workflow.add_edge(osint_node, verify_node)
        workflow.add_edge(analysis_node, verify_node)
        workflow.add_edge(db_node, verify_node)

        # Flujo de reintento
        workflow.add_conditional_edges(
            verify_node,
            lambda x: x["status"] == "failed",
            {verify_node: lambda x: x, retry_node: lambda x: x["task_result"]}
        )
        workflow.add_edge(retry_node, verify_node)

        # Nodo de inicio
        def start_task(task_description):
            """
            Inicia una tarea basada en la descripción.
            """
            print(f"🚀 Iniciando tarea: {task_description}")

            # Determinar qué herramienta usar
            if "osint" in task_description.lower():
                return osint_node.invoke({"query": task_description})
            elif "analizar archivo" in task_description.lower():
                return analysis_node.invoke({"file_path": "example.txt"})
            elif "consultar base de datos" in task_description.lower():
                return db_node.invoke({"query": task_description})
            else:
                return {"error": "Descripción de tarea no reconocida"}

        workflow.add_node(start_task)

        # Configurar el grafo
        workflow.set_entry_point(start_task)
        return workflow

    def _execute_task(self, task_description: str) -> Dict[str, Any]:
        """
        Ejecuta una tarea usando LangGraph.
        """
        result = self.graph.invoke(task_description)
        return result

    def _perform_osint_search(self, query: str) -> Dict[str, Any]:
        """
        Ejemplo de ejecución de búsqueda OSINT.
        """
        # Simular búsqueda OSINT
        time.sleep(1)
        return {
            "query": query,
            "results": [
                f"Resultado OSINT para: {query} (simulado)",
                f"Información adicional sobre: {query}"
            ],
            "timestamp": datetime.now().isoformat()
        }

    def _analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Ejemplo de análisis de archivo.
        """
        # Simular análisis de archivo
        time.sleep(1)
        return {
            "file_path": file_path,
            "analysis": f"Análisis del archivo {file_path} (simulado)",
            "metadata": {"size": "1KB", "type": "txt"}
        }

    def _query_database(self, query: str) -> Dict[str, Any]:
        """
        Ejemplo de consulta a la base de datos.
        """
        # Simular consulta a la base de datos
        time.sleep(1)
        return {
            "query": query,
            "results": [
                f"Resultado de la consulta: {query} (simulado)",
                f"Datos relevantes encontrados"
            ]
        }

    def run_task(self, task_description: str) -> Dict[str, Any]:
        """
        Ejecuta una tarea completa usando LangGraph.
        """
        return self._execute_task(task_description)

# Endpoint para ejecutar tareas usando LangGraph
@app.route('/api/langgraph/task', methods=['POST'])
def execute_langgraph_task():
    """
    Endpoint para ejecutar tareas usando LangGraph.
    """
    data = request.get_json()
    if not data or 'task_description' not in data:
        return jsonify({"status": "error", "message": "Descripción de tarea requerida"}), 400

    task_description = data['task_description']
    langgraph_manager = LangGraphManager()
    result = langgraph_manager.run_task(task_description)

    return jsonify({"status": "ok", "result": result})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5004, debug=False)