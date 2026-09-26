"""
GHOST_SCRAPER - Módulo de OSINT para AURA
Autor: Arquitecto
Versión: 1.0
Descripción: Herramienta de rastreo en redes sociales sin autenticación
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urlparse, quote

class OSINTScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.timeout = 10
        self.max_retries = 3
        self.social_platforms = {
            'twitter': 'twitter.com',
            'instagram': 'instagram.com',
            'facebook': 'facebook.com',
            'linkedin': 'linkedin.com',
            'reddit': 'reddit.com',
            'youtube': 'youtube.com'
        }

    def search_duckduckgo(self, query, max_results=5):
        """Realiza búsquedas en DuckDuckGo para obtener enlaces relevantes"""
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.text, 'html.parser')

            results = []
            for result in soup.select('.result__body a.result__url'):
                link = result.get('href')
                if link and not link.startswith('http'):
                    link = f"https://{link}"
                results.append(link)

            return results[:max_results]
        except Exception as e:
            print(f"Error en búsqueda DuckDuckGo: {e}")
            return []

    def scrape_social_media(self, target, platform):
        """Extrae información de redes sociales específicas"""
        if platform not in self.social_platforms:
            return {"error": f"Plataforma {platform} no soportada"}

        domain = self.social_platforms[platform]
        query = f"{target} site:{domain}"
        links = self.search_duckduckgo(query)

        results = []
        for link in links:
            try:
                response = requests.get(link, headers=self.headers, timeout=self.timeout)
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extraer información básica
                title = soup.title.string if soup.title else ""
                description = ""
                for meta in soup.find_all('meta', attrs={'name': 'description'}):
                    description = meta.get('content', '')

                # Extraer texto del cuerpo
                text_content = ""
                for element in soup.find_all(['p', 'article', 'div']):
                    if element.text.strip():
                        text_content += element.text.strip() + "\n"

                results.append({
                    "url": link,
                    "title": title,
                    "description": description,
                    "content": text_content.strip(),
                    "platform": platform
                })

            except Exception as e:
                print(f"Error al procesar {link}: {e}")
                continue

        return {"results": results}

    def perform_osint_search(self, target, platforms=None):
        """Realiza una búsqueda OSINT completa en múltiples plataformas"""
        if platforms is None:
            platforms = list(self.social_platforms.keys())

        all_results = []
        for platform in platforms:
            if platform in self.social_platforms:
                print(f"Buscando en {platform}...")
                results = self.scrape_social_media(target, platform)
                if results.get('results'):
                    all_results.extend(results['results'])

        return {
            "target": target,
            "platforms": platforms,
            "results": all_results,
            "timestamp": int(time.time())
        }

    def get_social_media_links(self, target):
        """Obtiene enlaces de redes sociales para un target específico"""
        links = {}
        for platform, domain in self.social_platforms.items():
            query = f"{target} {domain}"
            results = self.search_duckduckgo(query, max_results=3)
            links[platform] = list(set(results))  # Eliminar duplicados

        return links

# Ejemplo de uso
if __name__ == "__main__":
    scraper = OSINTScraper()
    target = "Elon Musk"
    platforms = ["twitter", "instagram"]

    print(f"Iniciando búsqueda OSINT para: {target}")
    results = scraper.perform_osint_search(target, platforms)

    print("\nResultados:")
    print(f"Target: {results['target']}")
    print(f"Plataformas: {', '.join(results['platforms'])}")
    print(f"Encontrados {len(results['results'])} resultados")

    for i, result in enumerate(results['results'], 1):
        print(f"\nResultado {i}:")
        print(f"URL: {result['url']}")
        print(f"Título: {result['title']}")
        print(f"Descripción: {result['description'][:100]}...")
        print(f"Contenido: {result['content'][:200]}...")