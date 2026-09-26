"""
GHOST_SCRAPER API - Endpoint para OSINT
Autor: Arquitecto
Versión: 1.0
Descripción: API para realizar búsquedas OSINT en redes sociales
"""

from flask import Flask, request, jsonify
from AURA_Core.osint_scraper import OSINTScraper
import json
import time

app = Flask(__name__)
scraper = OSINTScraper()

@app.route('/api/osint', methods=['POST'])
def perform_osint_search():
    """
    Endpoint para realizar búsquedas OSINT
    Requiere:
    - target: El nombre o término a buscar
    - platforms: Lista de plataformas (opcional)
    """
    try:
        data = request.get_json()
        target = data.get('target')
        platforms = data.get('platforms', None)

        if not target:
            return jsonify({'error': 'El parámetro "target" es obligatorio'}), 400

        print(f"Iniciando búsqueda OSINT para: {target}")

        # Realizar la búsqueda
        results = scraper.perform_osint_search(target, platforms)

        # Formatear resultados para JSON
        formatted_results = {
            'status': 'success',
            'target': results['target'],
            'platforms': results['platforms'],
            'results': results['results'],
            'timestamp': results['timestamp'],
            'message': f"Búsqueda OSINT completada para {target}"
        }

        return jsonify(formatted_results), 200

    except Exception as e:
        print(f"Error en búsqueda OSINT: {e}")
        return jsonify({
            'status': 'error',
            'message': f"Error al realizar la búsqueda OSINT: {str(e)}",
            'error': str(e)
        }), 500

@app.route('/api/osint/links', methods=['POST'])
def get_social_media_links():
    """
    Endpoint para obtener enlaces de redes sociales
    Requiere:
    - target: El nombre o término a buscar
    """
    try:
        data = request.get_json()
        target = data.get('target')

        if not target:
            return jsonify({'error': 'El parámetro "target" es obligatorio'}), 400

        print(f"Obteniendo enlaces de redes sociales para: {target}")

        # Obtener enlaces
        links = scraper.get_social_media_links(target)

        # Formatear resultados para JSON
        formatted_links = {
            'status': 'success',
            'target': target,
            'links': links,
            'timestamp': int(time.time()),
            'message': f"Enlaces de redes sociales obtenidos para {target}"
        }

        return jsonify(formatted_links), 200

    except Exception as e:
        print(f"Error al obtener enlaces de redes sociales: {e}")
        return jsonify({
            'status': 'error',
            'message': f"Error al obtener enlaces de redes sociales: {str(e)}",
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)