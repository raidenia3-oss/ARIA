import os
import sys
import json
from datetime import datetime
import requests

# Ensure imports are resolved correctly from the script directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from db.jarvis import JarvisDB

class JARVISCore:
    def __init__(self):
        self.db = JarvisDB()
        self.offline = True  # Assume offline initially
        self.model = "local"
        self.test_connectivity()
    
    def test_connectivity(self):
        """Detects if internet is available, prioritizing connectivity daemon cache"""
        status_file = os.path.join(BASE_DIR, 'cache', 'connectivity_status.json')
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # If cache is fresh (less than 6 minutes), use it
                last_check = datetime.fromisoformat(data["last_check"])
                delta = (datetime.now() - last_check).total_seconds()
                if delta < 360:
                    self.offline = not data.get("online", False)
                    return
            except Exception:
                pass  # Fallback to live check if reading fails
        
        try:
            # Short timeout to avoid hanging the startup process
            requests.get("https://www.google.com", timeout=2)
            self.offline = False
        except Exception:
            self.offline = True

    
    def process_input(self, user_input):
        """
        Processes user input:
        1. Intercepts web scraping requests (URLs, 'scrape', 'lee', 'conectar')
        2. Checks local cache
        3. If cached, returns it immediately
        4. If not cached, generates response (online or offline fallback)
        5. Saves the interaction to the DB and cache
        """
        # STEP 0: Check if user wants to scrape/connect to a URL
        normalized_input = user_input.lower().strip()
        url = None
        force_refresh = False
        
        if normalized_input.startswith("http://") or normalized_input.startswith("https://"):
            url = user_input.strip()
        elif "http://" in normalized_input or "https://" in normalized_input:
            # Extract URL
            words = user_input.split()
            for word in words:
                if word.startswith("http://") or word.startswith("https://"):
                    url = word.strip()
                    break
        elif normalized_input.startswith("conectar ") or normalized_input.startswith("scrape ") or normalized_input.startswith("lee "):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                potential_url = parts[1].strip()
                # Remove brackets/parentheses if user pasted them
                potential_url = potential_url.strip("()[]\"'")
                if not potential_url.startswith("http://") and not potential_url.startswith("https://"):
                    potential_url = "http://" + potential_url
                url = potential_url

        if url:
            from skills.web_connector import WebConnector
            connector = WebConnector(self.db, self)
            
            # Check for force refresh terms
            if "force" in normalized_input or "refrescar" in normalized_input:
                force_refresh = True
                
            scrape_res = connector.fetch_and_parse(url, force_refresh=force_refresh)
            
            banner = scrape_res.get("status_banner", "")
            title = scrape_res.get("title", "Sin Título")
            content = scrape_res.get("content", "")
            
            # Build clean response summary
            response = f"{banner}\n🌐 URL: {url}\n📝 Título: {title}\n\n=== CONTENIDO EXTRAÍDO ===\n{content[:1500]}\n"
            if len(content) > 1500:
                response += f"\n... [Muestra de 1500 caracteres, total: {len(content)} caracteres]"
            
            source = scrape_res.get("source", "local")
            self.db.save_conversation(user_input, response, f"web_{source}", offline=self.offline)
            return response

        # STEP 1: Search in Cache for standard conversation
        cached = self.db.get_cached_answer(user_input)
        if cached:
            # Save cached conversation
            self.db.save_conversation(user_input, cached, "cache", offline=True)
            return f"[CACHE HIT] {cached}"
        
        # STEP 2: Generate Response
        if self.offline:
            response = self._offline_response(user_input)
            source = "local"
        else:
            response = self._cloud_response(user_input)
            # If cloud returned fallback or failed, source is local
            if response.startswith("Necesito internet") or response.startswith("Error"):
                source = "local"
            else:
                source = "cloud"
        
        # STEP 3: Save to DB & Cache
        self.db.save_conversation(user_input, response, source, offline=self.offline)
        self.db.save_to_cache(user_input, response, source)
        
        return response
    
    def _offline_response(self, user_input):
        """Simple rules/responses when offline"""
        rules = {
            "hola": "Hola Raiden, soy JARVIS. ¿En qué puedo ayudarte?",
            "qué eres": "Soy JARVIS, tu asistente virtual. Estoy en tu celular.",
            "hora": f"Son las {datetime.now().strftime('%H:%M:%S')}",
            "ayuda": "Puedo: saludarte, responder preguntas simples, conectarme a internet cuando haya wifi",
        }
        
        normalized_input = user_input.lower().strip()
        for keyword, response in rules.items():
            if keyword in normalized_input:
                return response
        
        # Fallback
        return "Necesito internet para responder eso. Conecta wifi y reinténtalo."
    
    def _cloud_response(self, user_input):
        """Connects to HF Space API of AURA-inference"""
        try:
            # Direct URL of HF Space API
            hf_space_url = "https://raidenia3-oss-aura-inference.hf.space"
            
            response = requests.post(
                f"{hf_space_url}/api/predict",
                json={"data": [user_input]},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                # Gradio returns prediction as a list under 'data'
                if "data" in result and len(result["data"]) > 0:
                    return result["data"][0]
                return "Error: Formato de respuesta de HF Spaces inesperado."
            else:
                print(f"Cloud status code: {response.status_code}")
                return self._offline_response(user_input)
        
        except Exception as e:
            print(f"Cloud error: {e}")
            # Fallback to offline rules
            return self._offline_response(user_input)
    
    def sync_with_cloud(self):
        """Syncs conversations to Git repository and saves sync JSON file"""
        # Re-check connectivity
        self.test_connectivity()
        if self.offline:
            print("🔴 Sin internet, no puedo sincronizar")
            return
        
        try:
            # Fetch conversations from local DB
            self.db.cursor.execute('SELECT * FROM conversations')
            conversations = self.db.cursor.fetchall()
            
            # Format synchronization payload
            data = {
                "timestamp": datetime.now().isoformat(),
                "conversations": conversations,
                "device": "Honor X6d 5G"
            }
            
            # Save sync JSON inside the 'data' subfolder
            sync_dir = os.path.join(BASE_DIR, 'data')
            os.makedirs(sync_dir, exist_ok=True)
            sync_file = os.path.join(sync_dir, 'sync.json')
            
            with open(sync_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Push changes to Github
            print("Pushing data to GitHub...")
            os.system(f"cd {BASE_DIR} && git add . && git commit -m 'JARVIS sync' && git push")
            print("✅ Sincronizado con GitHub")
        
        except Exception as e:
            print(f"Sync error: {e}")
            
    def send_to_rocket(self, message, response):
        """Sends conversation snippets to Rocket.Chat (#jarvis-mobile) if online"""
        if self.offline:
            return  # Silently skip if offline
            
        try:
            webhook_url = "https://rocket.example.com/hooks/xxx"
            payload = {
                "text": f"📱 *Celular*\nTú: {message}\nJARVIS: {response}"
            }
            requests.post(webhook_url, json=payload, timeout=3)
        except Exception:
            pass
    
    def close(self):
        self.db.close()
