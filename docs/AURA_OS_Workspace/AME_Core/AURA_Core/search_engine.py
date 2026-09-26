"""
Módulo de búsqueda OSINT para AURA.
Utiliza duckduckgo_search para realizar búsquedas en diferentes plataformas.
"""

import os
from duckduckgo_search import ddg
from database_manager import save_osint_result

def handle_search_request(params):
    """
    Maneja una solicitud de búsqueda OSINT.

    Args:
        params (dict): Parámetros de la búsqueda:
            - query (str): Consulta a buscar.
            - target_platform (str): Plataforma objetivo (web, twitter, instagram).
            - max_results (int): Número máximo de resultados.

    Returns:
        dict: Resultados de la búsqueda en formato estructurado.
    """
    query = params.get('query', '').strip()
    target_platform = params.get('target_platform', 'web').lower()
    max_results = int(params.get('max_results', 5))

    if not query:
        return {
            "status": "error",
            "message": "La consulta de búsqueda no puede estar vacía"
        }

    try:
        # Configurar el operador DORK según la plataforma objetivo
        if target_platform == 'twitter':
            search_query = f"{query} site:twitter.com"
        elif target_platform == 'instagram':
            search_query = f"{query} site:instagram.com"
        else:  # web (búsqueda general)
            search_query = query

        # Realizar la búsqueda
        results = ddg(search_query, max_results=max_results)

        # Formatear los resultados
        formatted_results = []
        for result in results:
            formatted_results.append({
                "title": result.get('title', ''),
                "link": result.get('link', ''),
                "snippet": result.get('body', ''),
                "platform": target_platform
            })

        # Guardar cada resultado en la base de datos
        for result in formatted_results:
            save_osint_result(
                query=query,
                platform=target_platform,
                result_title=result.get('title', ''),
                snippet=result.get('snippet', ''),
                url=result.get('link', '')
            )

        return {
            "status": "success",
            "message": f"Búsqueda completada para '{query}' en {target_platform}",
            "results": formatted_results,
            "platform": target_platform,
            "query": query
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error en la búsqueda: {str(e)}",
            "error_details": str(e)
        }