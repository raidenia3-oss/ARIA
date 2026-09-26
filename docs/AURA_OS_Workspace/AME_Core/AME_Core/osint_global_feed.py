"""
Endpoint para el feed global OSINT.
Proporciona datos simulados de aviones, barcos y noticias geopolíticas.
"""

from flask import jsonify
import random
import time

def register_osint_global_feed(app):
    """
    Registra el endpoint para el feed global OSINT.
    """
    @app.route('/api/osint/global_feed')
    def api_osint_global_feed():
        """
        Endpoint para obtener datos OSINT simulados.
        Devuelve coordenadas de aviones, barcos y noticias geopolíticas.
        """
        try:
            # Simular datos de aviones
            aircraft = []
            for _ in range(random.randint(3, 10)):
                lat = random.uniform(-90, 90)
                lon = random.uniform(-180, 180)
                aircraft.append({
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "altitude": random.randint(10000, 45000),
                    "speed": random.randint(300, 900),
                    "icao24": f"AC{random.randint(1000, 9999)}"
                })

            # Simular datos de noticias geopolíticas
            news = [
                {
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "title": "🚨 Tensión en San Francisco: Protestas cerca del puerto",
                    "source": "GeoSentinel",
                    "severity": "high"
                },
                {
                    "lat": 52.5200,
                    "lon": 13.4050,
                    "title": "🇪🇺 Berlín: Nuevo acuerdo comercial con Asia",
                    "source": "Euronews",
                    "severity": "medium"
                },
                {
                    "lat": 34.0522,
                    "lon": -118.2437,
                    "title": "🇺🇸 Los Ángeles: Incendio forestal en progreso",
                    "source": "CalFire",
                    "severity": "critical"
                },
                {
                    "lat": 48.8566,
                    "lon": 2.3522,
                    "title": "🇫🇷 París: Manifestaciones por reforma laboral",
                    "source": "Le Monde",
                    "severity": "medium"
                },
                {
                    "lat": -33.8688,
                    "lon": 151.2093,
                    "title": "🇦🇺 Sídney: Alertas por tormentas eléctricas",
                    "source": "BOM Australia",
                    "severity": "high"
                }
            ]

            # Simular datos de barcos (opcional)
            ships = []
            for _ in range(random.randint(2, 5)):
                lat = random.uniform(-90, 90)
                lon = random.uniform(-180, 180)
                ships.append({
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "speed": random.uniform(0, 30),
                    "course": random.randint(0, 360),
                    "mmsi": f"MMSI{random.randint(1000000, 9999999)}"
                })

            # Retornar los datos simulados
            return jsonify({
                "status": "ok",
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
                "aircraft": aircraft,
                "ships": ships,
                "news": news,
                "source": "AURA OSINT Simulator"
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error generando feed OSINT: {str(e)}"
            }), 500