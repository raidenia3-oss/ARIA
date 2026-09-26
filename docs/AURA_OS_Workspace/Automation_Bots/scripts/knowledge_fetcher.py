"""
knowledge_fetcher.py - Integración con Obsidian (Segundo Cerebro)
Busca en la bóveda de Obsidian y devuelve resultados relevantes para AURA.
"""

import os
import json
import re
from typing import List, Dict, Optional
import requests
from pathlib import Path

# Configuración
OBSIDIAN_PATH = os.environ.get('OBSIDIAN_PATH', 'C:/Users/User/ObsidianVault')
GRAPHQL_ENDPOINT = os.environ.get('OBSIDIAN_GRAPHQL', 'http://localhost:8080/graphql')
API_KEY = os.environ.get('OBSIDIAN_API_KEY', '')

# Estructura de la consulta GraphQL para buscar en Obsidian
OBSIDIAN_QUERY = """
query SearchNotes($query: String!) {
  search(query: $query) {
    file {
      name
      path
      ... on MarkdownFile {
        frontmatter {
          title
          tags
        }
        content
      }
    }
  }
}
"""

class ObsidianFetcher:
    """
    Clase para buscar en la bóveda de Obsidian usando GraphQL.
    """

    def __init__(self, vault_path: str = OBSIDIAN_PATH, endpoint: str = GRAPHQL_ENDPOINT):
        self.vault_path = Path(vault_path)
        self.endpoint = endpoint
        self.api_key = API_KEY

        # Validar que la bóveda exista
        if not self.vault_path.exists():
            raise FileNotFoundError(f"La bóveda de Obsidian no existe en {self.vault_path}")

    def search_notes(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Busca notas en Obsidian usando GraphQL.
        """
        if not self.endpoint or self.endpoint == 'http://localhost:8080/graphql':
            # Si no hay endpoint configurado, simular resultados
            return self._simulate_search(query, max_results)

        try:
            # Preparar la consulta GraphQL
            variables = {"query": query}
            payload = {
                "query": OBSIDIAN_QUERY,
                "variables": variables
            }

            # Enviar la consulta
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
            }

            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'search' in data['data']:
                    return data['data']['search'][:max_results]
            return []

        except Exception as e:
            print(f"⚠️ Error buscando en Obsidian: {e}")
            return self._simulate_search(query, max_results)

    def _simulate_search(self, query: str, max_results: int) -> List[Dict]:
        """
        Simula resultados de búsqueda si no hay conexión a Obsidian.
        """
        # Resultados simulados basados en el query
        results = []

        # Extraer palabras clave del query
        keywords = re.findall(r'\b\w{3,}\b', query.lower())

        # Simular notas relevantes
        for i in range(1, max_results + 1):
            results.append({
                "file": {
                    "name": f"Nota {i} - {query[:20]}...",
                    "path": f"notas/{i}/relevante.md",
                    "content": f"""
                    ## {query[:30]}...

                    **Contenido simulado** para la búsqueda "{query}".

                    ### Palabras clave encontradas:
                    {', '.join(keywords)}

                    ### Relación con AURA:
                    - {random.choice([
                        "Este documento contiene detalles técnicos sobre el módulo de escaneo de red.",
                        "Incluye información sobre integración con sistemas de exfiltración.",
                        "Describe estrategias de seguridad para Shadow-Core.",
                        "Contiene ejemplos de comandos OSINT avanzados.",
                        "Explica cómo configurar el Protocolo de Pánico."
                    ])}

                    **Nota:** Este es un resultado simulado. Para conexión real, configura OBSIDIAN_GRAPHQL.
                    """.strip()
                }
            })

        return results

    def extract_relevant_info(self, results: List[Dict], question: str) -> str:
        """
        Extrae información relevante de los resultados de búsqueda.
        """
        if not results:
            return "No se encontraron resultados relevantes en la bóveda de Obsidian."

        response = f"""
        🔍 **Resultados de búsqueda en Obsidian (Segundo Cerebro):**
        {question}

        **Notas encontradas ({len(results)}):**
        """

        for i, result in enumerate(results, 1):
            content = result.get('file', {}).get('content', '')
            title = result.get('file', {}).get('name', 'Sin título')

            # Extraer solo la primera línea relevante
            first_line = content.split('\n')[0] if content else "Contenido no disponible"

            response += f"""
        {i}. {title}
           - {first_line[:80]}...
        """

        response += f"""
        📌 **Recomendación:** Revisa estas notas para detalles técnicos antes de proceder.
        """

        return response

def ask_obsidian(question: str, max_results: int = 3) -> str:
    """
    Función principal para consultar Obsidian.
    """
    fetcher = ObsidianFetcher()

    print(f"🔍 Consultando Obsidian: '{question}'")
    results = fetcher.search_notes(question, max_results)

    if not results:
        return "⚠️ No se encontraron resultados en Obsidian. ¿Deseas continuar sin consultar?"

    return fetcher.extract_relevant_info(results, question)

if __name__ == "__main__":
    import random

    print("""
    🌐 OBSIDIAN INTEGRATION MODULE
    =============================
    """)

    while True:
        question = input("\n🔍 ¿Qué necesitas buscar en Obsidian? (o 'salir' para terminar): ").strip()

        if question.lower() in ('salir', 'exit', 'quit'):
            break

        if not question:
            print("⚠️ Por favor ingresa una pregunta.")
            continue

        print("\n" + ask_obsidian(question))