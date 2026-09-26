#!/usr/bin/env python3
"""
github_scout.py: Script para buscar proyectos en GitHub relacionados con tecnologías de IA distribuida y agentes autónomos.

Este script utiliza la API pública de GitHub para buscar repositorios con keywords específicas,
filtrando por estrellas, fecha de actualización y lenguaje de programación.
"""

import requests
import datetime
from dateutil.relativedelta import relativedelta

# Configuración de la API de GitHub
GITHUB_API_URL = "https://api.github.com/search/repositories"
HEADERS = {
    "Accept": "application/vnd.github.v3+json"
}

# Palabras clave para la búsqueda
KEYWORDS = [
    "autonomous agent",
    "swarm AI",
    "distributed node",
    "self-healing system"
]

# Parámetros de filtrado
MIN_STARS = 100
DAYS_SINCE_LAST_UPDATE = 180  # 6 meses
LANGUAGES = ["python", "javascript"]

# Ruta del informe generado
REPORT_PATH = "C:\\Users\\User\\Downloads\\AURA\\github_scout_report.md"

def get_repositories():
    """Busca repositorios en GitHub según los criterios especificados."""
    repositories = []

    for keyword in KEYWORDS:
        query = f"{keyword} stars:>={MIN_STARS} language:{' OR language:'.join(LANGUAGES)}"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 30  # Máximo permitido por la API sin autenticación
        }

        try:
            response = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()

            for repo in data.get("items", []):
                last_update_date = datetime.datetime.strptime(repo["pushed_at"], "%Y-%m-%dT%H:%M:%SZ")
                days_since_update = (datetime.datetime.now() - last_update_date).days

                if days_since_update <= DAYS_SINCE_LAST_UPDATE:
                    repositories.append(repo)

        except requests.exceptions.RequestException as e:
            print(f"Error al buscar repositorios para '{keyword}': {e}")

    return repositories

def generate_report(repositories):
    """Genera un informe en formato Markdown con los repositorios encontrados."""
    report_content = f"""# Reporte de Proyectos GitHub Relacionados con IA Distribuida y Agentes Autónomos

**Fecha del reporte:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Criterios de Búsqueda
- **Palabras clave:** {', '.join(KEYWORDS)}
- **Mínimo de estrellas:** {MIN_STARS}
- **Última actualización:** Menos de {DAYS_SINCE_LAST_UPDATE} días
- **Lenguajes:** {', '.join(LANGUAGES)}

## Proyectos Recomendados

"""

    if not repositories:
        report_content += "No se encontraron repositorios que cumplan con los criterios de búsqueda."
    else:
        for idx, repo in enumerate(repositories, 1):
            repo_url = repo["html_url"]
            stars = repo["stargazers_count"]
            language = repo["language"]
            description = repo["description"] or "Sin descripción"
            last_update = datetime.datetime.strptime(repo["pushed_at"], "%Y-%m-%dT%H:%M:%SZ").strftime('%Y-%m-%d')

            report_content += f"""
### {idx}. [{repo['name']}]({repo_url})
**Descripción:** {description}
**Estrellas:** {stars}
**Lenguaje:** {language}
**Última actualización:** {last_update}
"""

    return report_content

def save_report(report_content):
    """Guarda el contenido del informe en un archivo."""
    try:
        with open(REPORT_PATH, "w", encoding="utf-8") as file:
            file.write(report_content)
        print(f"Informe guardado en {REPORT_PATH}")
    except IOError as e:
        print(f"Error al guardar el informe: {e}")

def main():
    """Función principal del script."""
    print("Buscando repositorios en GitHub...")
    repositories = get_repositories()

    if repositories:
        print(f"Se encontraron {len(repositories)} repositorios que cumplen con los criterios.")
    else:
        print("No se encontraron repositorios que cumplan con los criterios.")

    report_content = generate_report(repositories)
    save_report(report_content)

if __name__ == "__main__":
    main()