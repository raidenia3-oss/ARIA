import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
from datetime import datetime

class WebConnector:
    def __init__(self, db_manager, core_instance=None):
        self.db = db_manager
        self.core = core_instance
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3"
        }
        
    def fetch_and_parse(self, url, force_refresh=False):
        """
        Retrieves web content:
        1. Checks database cache first if offline or if force_refresh is False.
        2. If online and (not cached or force_refresh is True), performs requests HTTP GET.
        3. Cleans HTML content or formats JSON and writes to DB cache.
        4. If network fails, falls back to DB cache if available.
        """
        # Clean URL whitespace
        url = url.strip()
        
        # Check if URL scheme is present, default to http if missing
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.scheme:
            url = "http://" + url
            parsed_url = urllib.parse.urlparse(url)
            
        # 1. Check offline mode status
        is_offline = True
        if self.core:
            # Re-verify connectivity to be sure
            self.core.test_connectivity()
            is_offline = self.core.offline
            
        # 2. Check local DB cache first if not forcing a refresh
        if not force_refresh:
            cached_page = self.db.get_web_cache(url)
            if cached_page:
                cache_status = "[MODO OFFLINE - CACHE LOCAL]" if is_offline else "[CACHE HIT]"
                return {
                    "url": url,
                    "title": cached_page["title"],
                    "content": cached_page["content"],
                    "timestamp": cached_page["timestamp"],
                    "source": "cache",
                    "status_banner": f"ℹ️ {cache_status} Contenido guardado el {cached_page['timestamp']}"
                }
                
        # If offline and not found in cache, abort
        if is_offline:
            return {
                "url": url,
                "title": "Sin Conexión",
                "content": "No se puede acceder a la URL porque estás en modo offline y no existe una versión en caché local para este sitio.",
                "timestamp": datetime.now().isoformat(),
                "source": "offline_error",
                "status_banner": "🔴 Error: Sin conexión a internet y sin copia en caché local."
            }
            
        # 3. Perform Live HTTP Fetching
        try:
            print(f" (Conectando a {url})...")
            response = requests.get(url, headers=self.headers, timeout=10)
            
            # Raise exception for 4xx/5xx HTTP codes
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            title = parsed_url.netloc # Default title
            
            # A. Parse JSON if applicable
            if "application/json" in content_type:
                try:
                    data = response.json()
                    cleaned_content = json.dumps(data, indent=2, ensure_ascii=False)
                    title = f"API JSON - {parsed_url.netloc}"
                except Exception:
                    cleaned_content = response.text
                    
            # B. Parse HTML using BeautifulSoup
            else:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get Title
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()
                    
                # Clean scripts, styles, embedded elements
                for element in soup(["script", "style", "nav", "footer", "iframe", "noscript", "header"]):
                    element.decompose()
                    
                # Extract clean text
                lines = (line.strip() for line in soup.get_text().splitlines())
                # Group text blocks and remove empty lines
                chunks = (phrase for line in lines for phrase in line.split("  ") if phrase)
                cleaned_content = "\n".join(chunk for chunk in chunks if chunk)
                
                # Truncate content to avoid loading massive contents into the prompt (e.g. 50k chars limit)
                if len(cleaned_content) > 50000:
                    cleaned_content = cleaned_content[:50000] + "\n\n[Contenido truncado por longitud...]"
            
            # Save fetched content to SQLite web_cache
            headers_serialized = json.dumps(dict(response.headers))
            self.db.save_web_cache(url, title, cleaned_content, headers_serialized)
            
            return {
                "url": url,
                "title": title,
                "content": cleaned_content,
                "timestamp": datetime.now().isoformat(),
                "source": "network",
                "status_banner": f"✅ [ONLINE] Raspado exitoso desde la red el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            
        except Exception as e:
            # 4. Fallback to cache if request fails
            print(f"⚠️ Error al conectar con la red: {e}. Buscando fallback local...")
            cached_page = self.db.get_web_cache(url)
            if cached_page:
                return {
                    "url": url,
                    "title": cached_page["title"],
                    "content": cached_page["content"],
                    "timestamp": cached_page["timestamp"],
                    "source": "fallback_cache",
                    "status_banner": f"⚠️ [FALLBACK CACHE] Falló la red ({type(e).__name__}). Mostrando copia guardada el {cached_page['timestamp']}"
                }
            else:
                return {
                    "url": url,
                    "title": "Error de Conexión",
                    "content": f"No se pudo conectar a la URL y no hay copia local en caché. Error: {e}",
                    "timestamp": datetime.now().isoformat(),
                    "source": "network_error",
                    "status_banner": f"🔴 Error: No hay conexión a internet y no hay copia local para esta URL."
                }
