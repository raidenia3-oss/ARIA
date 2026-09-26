"""
AURA External Hub — Conexión a la Matriz Global
Módulo para consumir datos del mundo real de APIs públicas.
Implementa caché temporal para evitar rate limits y fallos de red.
"""

import os
import json
import time
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging
from logging.handlers import RotatingFileHandler

# Configuración de logging
def setup_logging():
    """Configura el sistema de logging con rotación de archivos."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, 'external_hub.log'),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    ))

    logger = logging.getLogger('external_hub')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger

logger = setup_logging()

class ExternalHub:
    """
    Hub de conexión a APIs externas con caché temporal.
    - Consume datos de fuentes públicas gratuitas
    - Implementa caché para evitar rate limits
    - Maneja errores de red y conexiones
    """

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600  # 1 hora en segundos
        self.session = None
        self.last_refresh_time = 0
        self.refresh_interval = 300  # 5 minutos en segundos

        # Configuración de APIs públicas
        self.api_sources = {
            'weather': {
                'name': 'OpenWeatherMap',
                'url': 'http://api.openweathermap.org/data/2.5/weather',
                'params': {
                    'q': 'Lima,PE',  # Ciudad por defecto
                    'appid': 'your_api_key_here',  # Reemplazar con clave real
                    'units': 'metric',
                    'lang': 'es'
                },
                'cache_key': 'weather_data',
                'error_message': 'No se pudo obtener datos climáticos'
            },
            'news': {
                'name': 'NewsAPI',
                'url': 'https://newsapi.org/v2/top-headlines',
                'params': {
                    'country': 'pe',
                    'category': 'technology',
                    'apiKey': 'your_api_key_here',  # Reemplazar con clave real
                    'pageSize': 5
                },
                'cache_key': 'news_headlines',
                'error_message': 'No se pudieron obtener noticias'
            },
            'space': {
                'name': 'NASA APOD',
                'url': 'https://api.nasa.gov/planetary/apod',
                'params': {
                    'api_key': 'your_api_key_here',  # Reemplazar con clave real
                    'date': datetime.now().strftime('%Y-%m-%d')
                },
                'cache_key': 'space_apod',
                'error_message': 'No se pudo obtener imagen del espacio'
            },
            'crypto': {
                'name': 'CryptoCompare',
                'url': 'https://min-api.cryptocompare.com/data/pricemulti',
                'params': {
                    'fsyms': 'BTC,ETH,XRP',
                    'tsyms': 'USD'
                },
                'cache_key': 'crypto_prices',
                'error_message': 'No se pudieron obtener precios de criptomonedas'
            },
            'time': {
                'name': 'WorldTimeAPI',
                'url': 'http://worldtimeapi.org/api/timezone/America/Lima',
                'params': {},
                'cache_key': 'world_time',
                'error_message': 'No se pudo obtener hora mundial'
            }
        }

        # Inicializar sesión HTTP asíncrona
        self._init_session()

    def _init_session(self):
        """Inicializa la sesión HTTP asíncrona."""
        try:
            self.session = aiohttp.ClientSession()
            logger.info("🌐 Sesión HTTP asíncrona inicializada")
        except Exception as e:
            logger.error(f"❌ Error inicializando sesión HTTP: {e}")
            self.session = None

    async def _fetch_data(self, source_name: str) -> Optional[Dict]:
        """
        Obtiene datos de una fuente externa con manejo de errores.
        """
        if not self.session:
            logger.error("⚠️  Sesión HTTP no disponible")
            return None

        source = self.api_sources.get(source_name)
        if not source:
            logger.error(f"⚠️  Fuente '{source_name}' no configurada")
            return None

        try:
            async with self.session.get(
                source['url'],
                params=source['params']
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'source': source_name,
                        'data': data,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'success'
                    }
                else:
                    logger.warning(f"⚠️  Error en API {source['name']}: Código {response.status}")
                    return {
                        'source': source_name,
                        'error': source['error_message'],
                        'status': 'error',
                        'status_code': response.status
                    }
        except aiohttp.ClientError as e:
            logger.error(f"❌ Error de conexión con {source['name']}: {e}")
            return {
                'source': source_name,
                'error': source['error_message'],
                'status': 'error',
                'exception': str(e)
            }
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error decodificando JSON de {source['name']}: {e}")
            return {
                'source': source_name,
                'error': 'Error decodificando respuesta',
                'status': 'error',
                'exception': str(e)
            }
        except Exception as e:
            logger.error(f"❌ Error inesperado con {source['name']}: {e}")
            return {
                'source': source_name,
                'error': 'Error inesperado',
                'status': 'error',
                'exception': str(e)
            }

    async def refresh_all_sources(self) -> Dict:
        """
        Refresca todos los datos de las fuentes externas.
        """
        if not self.session:
            return {'status': 'error', 'message': 'Sesión HTTP no disponible'}

        tasks = []
        for source_name in self.api_sources:
            task = asyncio.create_task(self._fetch_data(source_name))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados y actualizar caché
        world_state = {
            'timestamp': datetime.now().isoformat(),
            'sources': {},
            'status': 'partial_success' if any(isinstance(r, Exception) for r in results) else 'success'
        }

        for i, source_name in enumerate(self.api_sources):
            result = results[i]
            if isinstance(result, Exception):
                world_state['sources'][source_name] = {
                    'error': 'Error inesperado',
                    'status': 'error',
                    'exception': str(result)
                }
            else:
                self.cache[source_name] = result
                world_state['sources'][source_name] = result

        return world_state

    def get_cached_data(self, source_name: str) -> Optional[Dict]:
        """
        Obtiene datos de la caché si están disponibles y no han expirado.
        """
        cached = self.cache.get(source_name)
        if not cached:
            return None

        # Verificar si la caché ha expirado
        try:
            cache_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.now() - cache_time > timedelta(seconds=self.cache_ttl):
                return None
        except (KeyError, ValueError):
            return None

        return cached

    async def get_world_state(self) -> Dict:
        """
        Obtiene el estado del mundo con datos de todas las fuentes.
        Refresca automáticamente si la caché ha expirado.
        """
        world_state = {
            'timestamp': datetime.now().isoformat(),
            'sources': {},
            'status': 'loading'
        }

        # Verificar si es hora de refrescar
        if (datetime.now() - datetime.fromisoformat(self.last_refresh_time)).total_seconds() > self.refresh_interval:
            logger.info("🔄 Refrescando estado del mundo...")
            world_state = await self.refresh_all_sources()
            self.last_refresh_time = datetime.now().isoformat()
        else:
            # Usar datos de la caché si están disponibles
            for source_name in self.api_sources:
                cached = self.get_cached_data(source_name)
                if cached:
                    world_state['sources'][source_name] = cached
                else:
                    # Intentar obtener datos frescos si la caché está vacía o expirada
                    result = await self._fetch_data(source_name)
                    if result:
                        self.cache[source_name] = result
                        world_state['sources'][source_name] = result
                    else:
                        world_state['sources'][source_name] = {
                            'source': source_name,
                            'error': self.api_sources[source_name]['error_message'],
                            'status': 'error'
                        }

        # Añadir información de conexión
        world_state['connection'] = {
            'online': self.session is not None,
            'last_refresh': self.last_refresh_time,
            'cache_ttl': self.cache_ttl
        }

        return world_state

    async def get_source_data(self, source_name: str) -> Dict:
        """
        Obtiene datos específicos de una fuente.
        """
        # Intentar obtener de caché primero
        cached = self.get_cached_data(source_name)
        if cached:
            return cached

        # Si no está en caché, obtener datos frescos
        result = await self._fetch_data(source_name)
        if result:
            self.cache[source_name] = result
        return result or {
            'source': source_name,
            'error': self.api_sources.get(source_name, {}).get('error_message', 'Fuente no disponible'),
            'status': 'error'
        }

    async def close(self):
        """Cierra la sesión HTTP."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("🔌 Sesión HTTP cerrada")

# Función para obtener datos de ejemplo (sin dependencias externas)
async def get_example_world_state():
    """
    Genera datos de ejemplo para cuando no hay conexión a internet.
    """
    return {
        'timestamp': datetime.now().isoformat(),
        'sources': {
            'weather': {
                'source': 'weather',
                'data': {
                    'main': {
                        'temp': 22.5,
                        'humidity': 78,
                        'pressure': 1012
                    },
                    'weather': [{
                        'main': 'Clear',
                        'description': 'Cielo despejado'
                    }],
                    'wind': {
                        'speed': 3.6
                    }
                },
                'timestamp': datetime.now().isoformat(),
                'status': 'example_data'
            },
            'news': {
                'source': 'news',
                'data': {
                    'articles': [
                        {
                            'title': 'Ejemplo: Avances en inteligencia artificial',
                            'description': 'Investigadores logran nuevos hitos en modelos de lenguaje...',
                            'publishedAt': datetime.now().isoformat()
                        },
                        {
                            'title': 'Ejemplo: Nueva tecnología cuántica',
                            'description': 'Compañías compiten por desarrollar computadoras cuánticas...',
                            'publishedAt': datetime.now().isoformat()
                        }
                    ]
                },
                'timestamp': datetime.now().isoformat(),
                'status': 'example_data'
            },
            'space': {
                'source': 'space',
                'data': {
                    'title': 'Ejemplo: Nebulosa de Orión',
                    'explanation': 'Una de las nebulosas más brillantes del cielo nocturno...',
                    'url': 'https://example.com/orion.jpg',
                    'hdurl': 'https://example.com/orion_hd.jpg'
                },
                'timestamp': datetime.now().isoformat(),
                'status': 'example_data'
            },
            'crypto': {
                'source': 'crypto',
                'data': {
                    'BTC': {
                        'USD': 50000.50
                    },
                    'ETH': {
                        'USD': 3000.75
                    },
                    'XRP': {
                        'USD': 0.85
                    }
                },
                'timestamp': datetime.now().isoformat(),
                'status': 'example_data'
            },
            'time': {
                'source': 'time',
                'data': {
                    'datetime': datetime.now().isoformat(),
                    'timezone': 'America/Lima',
                    'day_of_week': datetime.now().strftime('%A'),
                    'day_of_year': datetime.now().timetuple().tm_yday
                },
                'timestamp': datetime.now().isoformat(),
                'status': 'example_data'
            }
        },
        'connection': {
            'online': False,
            'last_refresh': datetime.now().isoformat(),
            'cache_ttl': 3600,
            'message': 'Sin conexión a internet. Mostrando datos de ejemplo.'
        }
    }

# Bloque de prueba
if __name__ == "__main__":
    import asyncio

    async def test_external_hub():
        hub = ExternalHub()

        # Probar obtención de estado del mundo
        world_state = await hub.get_world_state()
        print("Estado del mundo:")
        print(json.dumps(world_state, indent=2, ensure_ascii=False))

        # Probar obtención de datos específicos
        weather_data = await hub.get_source_data('weather')
        print("\nDatos climáticos:")
        print(json.dumps(weather_data, indent=2, ensure_ascii=False))

        # Cerrar sesión
        await hub.close()

    asyncio.run(test_external_hub())